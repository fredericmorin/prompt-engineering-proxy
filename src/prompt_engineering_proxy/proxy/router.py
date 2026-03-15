"""Proxy route registration for /{server-slug}/v1/* and /{server-slug}/api/* endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from prompt_engineering_proxy.proxy.handler import proxy_request
from prompt_engineering_proxy.proxy.protocols.anthropic import AnthropicHandler
from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler
from prompt_engineering_proxy.proxy.protocols.ollama_chat import OllamaChatHandler
from prompt_engineering_proxy.proxy.protocols.ollama_generate import OllamaGenerateHandler
from prompt_engineering_proxy.proxy.protocols.openai_chat import OpenAIChatHandler
from prompt_engineering_proxy.proxy.protocols.openai_responses import OpenAIResponsesHandler
from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.services import ServerService

router = APIRouter()

_openai_chat = OpenAIChatHandler()
_openai_responses = OpenAIResponsesHandler()
_anthropic = AnthropicHandler()
_ollama_chat = OllamaChatHandler()
_ollama_generate = OllamaGenerateHandler()

# Maps the LLM endpoint path (after /v1/) to its protocol handler.
_HANDLER_FOR_PATH: dict[str, ProtocolHandler] = {
    "chat/completions": _openai_chat,
    "responses": _openai_responses,
    "messages": _anthropic,
}

# Maps Ollama API paths (after /api/) to their protocol handlers.
_OLLAMA_HANDLER_FOR_PATH: dict[str, ProtocolHandler] = {
    "chat": _ollama_chat,
    "generate": _ollama_generate,
}


@router.post("/{server_slug}/v1/{path:path}")
async def prefixed_proxy(request: Request, server_slug: str, path: str) -> Response:
    """Proxy POST /{server-slug}/v1/{path} → the specific upstream server identified by slug.

    Clients can target a specific configured server by using its name-derived slug as a
    URL prefix instead of relying on the default-server fallback.

    Example: server named "OpenAI Prod" → base URL http://localhost:8000/openai-prod/v1
    """
    handler = _HANDLER_FOR_PATH.get(path)
    if handler is None:
        return JSONResponse(
            {"error": f"Unsupported endpoint: /v1/{path}"},
            status_code=404,
        )

    db: Database = request.app.state.db
    repo = ServerService(db)
    server = await repo.get_by_slug(server_slug)
    if server is None:
        return JSONResponse(
            {"error": f"No server found with slug '{server_slug}'"},
            status_code=404,
        )

    return await proxy_request(
        request,
        handler,
        server_id=str(server["id"]),
        upstream_path=f"/v1/{path}",
    )


@router.post("/{server_slug}/api/{path:path}")
async def ollama_prefixed_proxy(request: Request, server_slug: str, path: str) -> Response:
    """Proxy POST /{server-slug}/api/{path} → Ollama upstream server identified by slug.

    Clients target Ollama servers using the name-derived slug as a URL prefix.

    Example: server named "Ollama Local" → base URL http://localhost:8000/ollama-local/api
    """
    handler = _OLLAMA_HANDLER_FOR_PATH.get(path)
    if handler is None:
        return JSONResponse(
            {"error": f"Unsupported Ollama endpoint: /api/{path}"},
            status_code=404,
        )

    db: Database = request.app.state.db
    repo = ServerService(db)
    server = await repo.get_by_slug(server_slug)
    if server is None:
        return JSONResponse(
            {"error": f"No server found with slug '{server_slug}'"},
            status_code=404,
        )

    return await proxy_request(
        request,
        handler,
        server_id=str(server["id"]),
        upstream_path=f"/api/{path}",
    )
