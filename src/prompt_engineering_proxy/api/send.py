"""Management API — send new requests and replay captured ones."""

import asyncio
import json
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler
from prompt_engineering_proxy.proxy.protocols.ollama_chat import OllamaChatHandler
from prompt_engineering_proxy.proxy.protocols.ollama_generate import OllamaGenerateHandler
from prompt_engineering_proxy.proxy.protocols.openai_chat import OpenAIChatHandler
from prompt_engineering_proxy.proxy.streaming import tee_ndjson_stream, tee_sse_stream
from prompt_engineering_proxy.realtime.events import (
    CHANNEL_REQUESTS,
    REQUEST_COMPLETED,
    REQUEST_ERROR,
    REQUEST_STARTED,
    ProxyEvent,
)
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.models import ProxyRequest
from prompt_engineering_proxy.storage.repository import RequestRepository, ServerRepository

router = APIRouter()

_PROTOCOL_PATHS: dict[str, str] = {
    "openai_chat": "/v1/chat/completions",
    "openai_responses": "/v1/responses",
    "anthropic": "/v1/messages",
    "ollama_chat": "/api/chat",
    "ollama_generate": "/api/generate",
}

_PROTOCOL_HANDLERS: dict[str, ProtocolHandler] = {
    "openai_chat": OpenAIChatHandler(),
    "ollama_chat": OllamaChatHandler(),
    "ollama_generate": OllamaGenerateHandler(),
}


def _redact_auth(headers: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower in ("authorization", "x-api-key"):
            token = value.removeprefix("Bearer ").strip()
            if len(token) > 8:
                redacted = f"{token[:4]}...{token[-4:]}"
                result[key] = f"Bearer {redacted}" if value.lower().startswith("bearer ") else redacted
            else:
                result[key] = "[REDACTED]"
        else:
            result[key] = value
    return result


class SendRequest(BaseModel):
    server_id: str
    body: dict[str, Any]
    stream: bool = False


class ReplayRequest(BaseModel):
    body: dict[str, Any] | None = None  # optional overrides to merge into original
    stream: bool = False


async def _execute_request(
    request: Request,
    server_id: str,
    body: dict[str, Any],
    parent_id: str | None = None,
    stream: bool = False,
) -> JSONResponse:
    db: Database = request.app.state.db
    publisher: RedisPublisher = request.app.state.redis
    http_client: httpx.AsyncClient = request.app.state.http_client

    repo_server = ServerRepository(db)
    server = await repo_server.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    protocol = str(server.get("protocol", "openai_chat"))
    path = _PROTOCOL_PATHS.get(protocol, "/v1/chat/completions")
    upstream_url = str(server["base_url"]).rstrip("/") + path

    forward_headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = server.get("api_key")
    if isinstance(api_key, str) and api_key:
        if protocol == "anthropic":
            forward_headers["x-api-key"] = api_key
            forward_headers["anthropic-version"] = "2023-06-01"
        else:
            forward_headers["Authorization"] = f"Bearer {api_key}"

    handler: ProtocolHandler = _PROTOCOL_HANDLERS.get(protocol, OpenAIChatHandler())
    model = handler.extract_model(body)

    if stream:
        # Send with streaming — return request_id immediately, run in background
        body = {**body, "stream": True}
        body_bytes = json.dumps(body).encode()

        repo_req = RequestRepository(db)
        proxy_req = ProxyRequest(
            protocol=protocol,
            method="POST",
            path=path,
            request_headers=json.dumps(_redact_auth(forward_headers)),
            request_body=json.dumps(body),
            is_streaming=True,
            model=model,
            server_id=server_id,
            parent_id=parent_id,
        )
        await repo_req.create(proxy_req)
        await publisher.publish(
            CHANNEL_REQUESTS,
            ProxyEvent(type=REQUEST_STARTED, request_id=proxy_req.id),
        )

        # Start streaming in background task
        upstream_request = http_client.build_request(
            method="POST",
            url=upstream_url,
            headers=forward_headers,
            content=body_bytes,
        )
        start_time = time.monotonic()
        try:
            upstream_response = await http_client.send(upstream_request, stream=True)
        except httpx.RequestError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await repo_req.update(proxy_req.id, error=str(exc), duration_ms=duration_ms)
            await publisher.publish(
                CHANNEL_REQUESTS,
                ProxyEvent(type=REQUEST_ERROR, request_id=proxy_req.id, data={"error": str(exc)}),
            )
            raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc

        _stream_fn = tee_ndjson_stream if handler.streaming_format == "ndjson" else tee_sse_stream

        async def _drain_stream() -> None:
            async for _ in _stream_fn(
                upstream_response=upstream_response,
                publisher=publisher,
                request_id=proxy_req.id,
                repo=repo_req,
                handler=handler,
                start_time=start_time,
            ):
                pass  # chunks already published to Redis and stored

        asyncio.create_task(_drain_stream())

        return JSONResponse(
            content={
                "request_id": proxy_req.id,
                "parent_id": parent_id,
                "streaming": True,
            }
        )

    # Non-streaming path
    body = {**body, "stream": False}
    body_bytes = json.dumps(body).encode()

    repo_req = RequestRepository(db)
    proxy_req = ProxyRequest(
        protocol=protocol,
        method="POST",
        path=path,
        request_headers=json.dumps(_redact_auth(forward_headers)),
        request_body=json.dumps(body),
        is_streaming=False,
        model=model,
        server_id=server_id,
        parent_id=parent_id,
    )
    await repo_req.create(proxy_req)
    await publisher.publish(
        CHANNEL_REQUESTS,
        ProxyEvent(type=REQUEST_STARTED, request_id=proxy_req.id),
    )

    start_time = time.monotonic()
    try:
        resp = await http_client.request("POST", upstream_url, headers=forward_headers, content=body_bytes)
    except httpx.RequestError as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        await repo_req.update(proxy_req.id, error=str(exc), duration_ms=duration_ms)
        await publisher.publish(
            CHANNEL_REQUESTS,
            ProxyEvent(type=REQUEST_ERROR, request_id=proxy_req.id, data={"error": str(exc)}),
        )
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc

    duration_ms = int((time.monotonic() - start_time) * 1000)
    try:
        response_body: dict[str, Any] = resp.json()
        response_body_str = json.dumps(response_body)
    except Exception:
        response_body = {}
        response_body_str = resp.text

    prompt_tokens, completion_tokens = handler.extract_usage(response_body)
    await repo_req.update(
        proxy_req.id,
        response_status=resp.status_code,
        response_headers=json.dumps(dict(resp.headers)),
        response_body=response_body_str,
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    await publisher.publish(
        CHANNEL_REQUESTS,
        ProxyEvent(
            type=REQUEST_COMPLETED,
            request_id=proxy_req.id,
            data={"status": resp.status_code},
        ),
    )

    return JSONResponse(
        content={
            "request_id": proxy_req.id,
            "parent_id": parent_id,
            "status": resp.status_code,
            "body": response_body,
            "duration_ms": duration_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
    )


@router.post("/send")
async def send_request(request: Request, body: SendRequest) -> JSONResponse:
    """Send a new composed request to an upstream server."""
    return await _execute_request(request, body.server_id, body.body, stream=body.stream)


@router.post("/requests/{request_id}/replay")
async def replay_request(request: Request, request_id: str, body: ReplayRequest) -> JSONResponse:
    """Replay a captured request, optionally with body overrides."""
    db: Database = request.app.state.db
    repo = RequestRepository(db)
    original = await repo.get(request_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Request not found")

    server_id = original.get("server_id")
    if not isinstance(server_id, str) or not server_id:
        raise HTTPException(status_code=400, detail="Original request has no associated server")

    original_body: dict[str, Any] = json.loads(str(original["request_body"]))
    if body.body:
        original_body.update(body.body)

    return await _execute_request(request, server_id, original_body, parent_id=request_id, stream=body.stream)
