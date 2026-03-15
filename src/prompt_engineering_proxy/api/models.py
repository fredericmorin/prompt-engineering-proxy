"""Management API — fetch model list from upstream server."""

import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.services import ServerService

router = APIRouter()


async def _fetch_loaded_models(
    http_client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
) -> set[str]:
    """Try to fetch currently-loaded models from Ollama's /api/ps endpoint."""
    try:
        resp = await http_client.get(f"{base_url}/api/ps", headers=headers, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            return {m.get("model", m.get("name", "")) for m in models if isinstance(m, dict)}
    except Exception:  # noqa: BLE001
        pass
    return set()


@router.get("/servers/{server_id}/models")
async def list_server_models(request: Request, server_id: str) -> JSONResponse:
    db: Database = request.app.state.db
    http_client: httpx.AsyncClient = request.app.state.http_client

    repo = ServerService(db)
    server = await repo.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    base_url = str(server["base_url"]).rstrip("/")
    headers: dict[str, str] = {}
    api_key = server.get("api_key")
    if isinstance(api_key, str) and api_key:
        protocol = str(server.get("protocol", ""))
        if protocol == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    protocol = str(server.get("protocol", ""))
    is_ollama = protocol in ("ollama_chat", "ollama_generate")

    try:
        if is_ollama:
            models_resp, loaded_names = await asyncio.gather(
                http_client.get(f"{base_url}/api/tags", headers=headers),
                _fetch_loaded_models(http_client, base_url, headers),
            )
            models_resp.raise_for_status()
            data = models_resp.json()
            # Ollama format: {"models": [{"name": "...", "model": "...", ...}]}
            raw_models = data.get("models", []) if isinstance(data, dict) else []
            models: list[dict[str, object]] = [
                {
                    **m,
                    "id": str(m.get("name", m.get("model", ""))),
                    "loaded": str(m.get("name", m.get("model", ""))) in loaded_names,
                }
                for m in raw_models
                if isinstance(m, dict)
            ]
        else:
            models_resp, loaded_names = await asyncio.gather(
                http_client.get(f"{base_url}/v1/models", headers=headers),
                _fetch_loaded_models(http_client, base_url, headers),
            )
            models_resp.raise_for_status()
            data = models_resp.json()
            # OpenAI format: {"data": [...], "object": "list"}
            raw = data.get("data", data) if isinstance(data, dict) else data
            if loaded_names:
                models = [
                    {**m, "loaded": str(m.get("id", "")) in loaded_names} if isinstance(m, dict) else m for m in raw
                ]
            else:
                models = raw

        return JSONResponse(content={"models": models})
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Upstream error: {exc.response.text[:200]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}") from exc


@router.delete("/servers/{server_id}/models/{model_name:path}")
async def unload_model(request: Request, server_id: str, model_name: str) -> JSONResponse:
    """Unload a model from an Ollama server (sets keep_alive=0)."""
    db: Database = request.app.state.db
    http_client: httpx.AsyncClient = request.app.state.http_client

    repo = ServerService(db)
    server = await repo.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    base_url = str(server["base_url"]).rstrip("/")
    headers: dict[str, str] = {}
    api_key = server.get("api_key")
    if isinstance(api_key, str) and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = await http_client.post(
            f"{base_url}/api/generate",
            json={"model": model_name, "keep_alive": 0},
            headers=headers,
        )
        resp.raise_for_status()
        return JSONResponse(content={"unloaded": True, "model": model_name})
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Upstream error: {exc.response.text[:200]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to unload model: {exc}") from exc
