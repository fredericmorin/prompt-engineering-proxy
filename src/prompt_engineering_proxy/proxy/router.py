"""Proxy route registration for /v1/* endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from prompt_engineering_proxy.proxy.handler import proxy_request
from prompt_engineering_proxy.proxy.protocols.openai_chat import OpenAIChatHandler

router = APIRouter()

_openai_chat = OpenAIChatHandler()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Proxy POST /v1/chat/completions → upstream OpenAI Chat Completions API."""
    return await proxy_request(request, _openai_chat)
