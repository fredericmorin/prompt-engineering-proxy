"""Management API — fetch model list from upstream server."""

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.repository import ServerRepository

router = APIRouter()


@router.get("/servers/{server_id}/models")
async def list_server_models(request: Request, server_id: str) -> JSONResponse:
    db: Database = request.app.state.db
    http_client: httpx.AsyncClient = request.app.state.http_client

    repo = ServerRepository(db)
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

    try:
        resp = await http_client.get(f"{base_url}/v1/models", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        # OpenAI format: {"data": [...], "object": "list"}
        models = data.get("data", data) if isinstance(data, dict) else data
        return JSONResponse(content={"models": models})
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Upstream error: {exc.response.text[:200]}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}") from exc
