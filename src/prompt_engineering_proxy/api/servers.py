"""Management API — server configuration CRUD."""

import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.models import Server
from prompt_engineering_proxy.storage.repository import ServerRepository

router = APIRouter()

_VALID_PROTOCOLS = {"openai_chat", "openai_responses", "anthropic", "ollama_chat", "ollama_generate"}


def _get_repo(request: Request) -> ServerRepository:
    db: Database = request.app.state.db
    return ServerRepository(db)


def _redact_server(server: dict[str, object]) -> dict[str, object]:
    result = dict(server)
    key = result.get("api_key")
    if isinstance(key, str) and key:
        result["api_key"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "[REDACTED]"
    return result


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def _validate_proxy_slug(slug: str | None) -> str | None:
    if slug is None or slug == "":
        return None
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=422,
            detail="proxy_slug must be lowercase alphanumeric with hyphens and start with a letter or digit",
        )
    return slug


class ServerCreate(BaseModel):
    name: str
    base_url: str
    protocol: str
    api_key: str | None = None
    proxy_slug: str | None = None
    is_default: bool = False


class ServerUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    protocol: str | None = None
    api_key: str | None = None
    proxy_slug: str | None = None
    is_default: bool | None = None


@router.get("/servers")
async def list_servers(request: Request) -> JSONResponse:
    repo = _get_repo(request)
    servers = await repo.list_all()
    return JSONResponse(content=[_redact_server(s) for s in servers])


@router.post("/servers", status_code=201)
async def create_server(request: Request, body: ServerCreate) -> JSONResponse:
    if body.protocol not in _VALID_PROTOCOLS:
        raise HTTPException(status_code=422, detail=f"Invalid protocol: {body.protocol}")
    data = body.model_dump()
    data["proxy_slug"] = _validate_proxy_slug(body.proxy_slug)
    repo = _get_repo(request)
    if body.is_default:
        await repo.clear_default()
    server = Server(**data)
    await repo.create(server)
    created = await repo.get(server.id)
    return JSONResponse(content=_redact_server(created or {}), status_code=201)


@router.get("/servers/{server_id}")
async def get_server(request: Request, server_id: str) -> JSONResponse:
    repo = _get_repo(request)
    server = await repo.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return JSONResponse(content=_redact_server(server))


@router.put("/servers/{server_id}")
async def update_server(request: Request, server_id: str, body: ServerUpdate) -> JSONResponse:
    repo = _get_repo(request)
    if await repo.get(server_id) is None:
        raise HTTPException(status_code=404, detail="Server not found")
    updates = body.model_dump(exclude_unset=True)
    if updates.get("protocol") and updates["protocol"] not in _VALID_PROTOCOLS:
        raise HTTPException(status_code=422, detail=f"Invalid protocol: {updates['protocol']}")
    if "proxy_slug" in updates:
        updates["proxy_slug"] = _validate_proxy_slug(updates["proxy_slug"])
    if updates.get("is_default"):
        await repo.clear_default()
    if updates:
        await repo.update(server_id, **updates)
    updated = await repo.get(server_id)
    return JSONResponse(content=_redact_server(updated or {}))


@router.delete("/servers/{server_id}", status_code=204)
async def delete_server(request: Request, server_id: str) -> Response:
    repo = _get_repo(request)
    if await repo.get(server_id) is None:
        raise HTTPException(status_code=404, detail="Server not found")
    await repo.delete(server_id)
    return Response(status_code=204)
