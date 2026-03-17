"""Proxy route registration for /{server-slug}/v1/* and /{server-slug}/api/* endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from prompt_engineering_proxy.proxy.handler import passthrough_proxy, proxy_request
from prompt_engineering_proxy.proxy.protocols import PROTOCOL_HANDLERS
from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler
from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.services import ServerService

router = APIRouter()

# Maps the LLM endpoint path (after /v1/) to its protocol handler.
_HANDLER_FOR_PATH: dict[str, ProtocolHandler] = {
    "chat/completions": PROTOCOL_HANDLERS["openai_chat"],
    "responses": PROTOCOL_HANDLERS["openai_responses"],
    "messages": PROTOCOL_HANDLERS["anthropic"],
}

# Maps Ollama API paths (after /api/) to their protocol handlers.
_OLLAMA_HANDLER_FOR_PATH: dict[str, ProtocolHandler] = {
    "chat": PROTOCOL_HANDLERS["ollama_chat"],
    "generate": PROTOCOL_HANDLERS["ollama_generate"],
}


@router.post("/{server_slug}/v1/{path:path}")
async def prefixed_proxy(request: Request, server_slug: str, path: str) -> Response:
    """Proxy POST /{server-slug}/v1/{path} → the specific upstream server identified by slug.

    Generation endpoints (chat/completions, responses, messages) are intercepted and stored.
    All other POST paths are forwarded transparently without recording.
    """
    handler = _HANDLER_FOR_PATH.get(path)

    db: Database = request.app.state.db
    repo = ServerService(db)
    server = await repo.get_by_slug(server_slug)
    if server is None:
        return JSONResponse(
            {"error": f"No server found with slug '{server_slug}'"},
            status_code=404,
        )

    if handler is None:
        return await passthrough_proxy(request, server, f"/v1/{path}")

    return await proxy_request(
        request,
        handler,
        server_id=server.id,
        upstream_path=f"/v1/{path}",
    )


@router.post("/{server_slug}/api/{path:path}")
async def ollama_prefixed_proxy(request: Request, server_slug: str, path: str) -> Response:
    """Proxy POST /{server-slug}/api/{path} → Ollama upstream server identified by slug.

    Generation endpoints (chat, generate) are intercepted and stored.
    All other POST paths are forwarded transparently without recording.
    """
    handler = _OLLAMA_HANDLER_FOR_PATH.get(path)

    db: Database = request.app.state.db
    repo = ServerService(db)
    server = await repo.get_by_slug(server_slug)
    if server is None:
        return JSONResponse(
            {"error": f"No server found with slug '{server_slug}'"},
            status_code=404,
        )

    if handler is None:
        return await passthrough_proxy(request, server, f"/api/{path}")

    return await proxy_request(
        request,
        handler,
        server_id=server.id,
        upstream_path=f"/api/{path}",
    )


@router.get("/{server_slug}/api/{full_path:path}")
@router.get("/{server_slug}/v1/{full_path:path}")
async def api_get_passthrough(request: Request, server_slug: str, full_path: str = "") -> Response:
    """Proxy GET /{server-slug}/v1/* and /{server-slug}/api/* to the upstream server.

    Enables transparent passthrough of read-only support endpoints such as:
    - GET /v1/models  (OpenAI, Anthropic)
    - GET /api/tags   (Ollama — list available models)
    - GET /api/ps     (Ollama — list loaded models)
    """
    db: Database = request.app.state.db
    repo = ServerService(db)
    server = await repo.get_by_slug(server_slug)
    if server is None:
        return JSONResponse(
            {"error": f"No server found with slug '{server_slug}'"},
            status_code=404,
        )

    raw_path = str(request.url.path)
    # Reconstruct the upstream path by stripping the server slug prefix
    slug_prefix = f"/{server_slug}"
    upstream_path = raw_path[len(slug_prefix) :] if raw_path.startswith(slug_prefix) else raw_path

    return await passthrough_proxy(request, server, upstream_path)
