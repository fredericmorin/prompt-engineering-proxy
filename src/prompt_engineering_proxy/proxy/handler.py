"""Core proxy logic: intercept → forward → tee → store."""

import json
import logging
import time
from typing import Any

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler
from prompt_engineering_proxy.proxy.streaming import tee_sse_stream
from prompt_engineering_proxy.realtime.events import (
    CHANNEL_REQUESTS,
    REQUEST_ERROR,
    REQUEST_STARTED,
    ProxyEvent,
)
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.models import ProxyRequest
from prompt_engineering_proxy.storage.repository import RequestRepository, ServerRepository

logger = logging.getLogger(__name__)

# HTTP hop-by-hop headers to strip when forwarding responses
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }
)

# Request headers not forwarded to upstream
_SKIP_REQUEST_HEADERS = frozenset({"host", "content-length"})


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact API key values: show first 4 + last 4 chars only."""
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


async def _get_upstream_url(db: Database, protocol: str) -> str | None:
    """Return base URL of the default (or first) server matching the protocol."""
    repo = ServerRepository(db)
    servers = await repo.list_all()
    default = next((s for s in servers if s["protocol"] == protocol and s["is_default"]), None)
    if default:
        return str(default["base_url"])
    first = next((s for s in servers if s["protocol"] == protocol), None)
    return str(first["base_url"]) if first else None


async def proxy_request(request: Request, handler: ProtocolHandler) -> Response:
    """Intercept an incoming LLM request, forward it upstream, capture and store the result."""
    db: Database = request.app.state.db
    publisher: RedisPublisher = request.app.state.redis
    http_client: httpx.AsyncClient = request.app.state.http_client

    upstream_base = await _get_upstream_url(db, handler.protocol_name)
    if not upstream_base:
        return JSONResponse(
            {"error": f"No upstream server configured for protocol '{handler.protocol_name}'"},
            status_code=503,
        )

    body_bytes = await request.body()
    try:
        body: dict[str, Any] = json.loads(body_bytes)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON request body"}, status_code=400)

    is_streaming = bool(body.get("stream", False))
    model = handler.extract_model(body)

    forward_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _SKIP_REQUEST_HEADERS
    }

    repo = RequestRepository(db)
    proxy_req = ProxyRequest(
        protocol=handler.protocol_name,
        method=request.method,
        path=str(request.url.path),
        request_headers=json.dumps(_redact_headers(dict(forward_headers))),
        request_body=json.dumps(body),
        is_streaming=is_streaming,
        model=model,
    )
    await repo.create(proxy_req)

    await publisher.publish(
        CHANNEL_REQUESTS,
        ProxyEvent(type=REQUEST_STARTED, request_id=proxy_req.id),
    )

    upstream_url = upstream_base.rstrip("/") + str(request.url.path)
    if request.url.query:
        upstream_url += "?" + request.url.query

    start_time = time.monotonic()

    if is_streaming:
        return await _handle_streaming(
            http_client=http_client,
            upstream_url=upstream_url,
            forward_headers=forward_headers,
            body_bytes=body_bytes,
            publisher=publisher,
            request_id=proxy_req.id,
            repo=repo,
            handler=handler,
            start_time=start_time,
        )
    return await _handle_non_streaming(
        http_client=http_client,
        upstream_url=upstream_url,
        forward_headers=forward_headers,
        body_bytes=body_bytes,
        publisher=publisher,
        request_id=proxy_req.id,
        repo=repo,
        handler=handler,
        start_time=start_time,
    )


async def _handle_non_streaming(
    http_client: httpx.AsyncClient,
    upstream_url: str,
    forward_headers: dict[str, str],
    body_bytes: bytes,
    publisher: RedisPublisher,
    request_id: str,
    repo: RequestRepository,
    handler: ProtocolHandler,
    start_time: float,
) -> Response:
    try:
        resp = await http_client.request(
            method="POST",
            url=upstream_url,
            headers=forward_headers,
            content=body_bytes,
        )
    except httpx.RequestError as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        await repo.update(request_id, error=str(exc), duration_ms=duration_ms)
        await publisher.publish(
            CHANNEL_REQUESTS,
            ProxyEvent(type=REQUEST_ERROR, request_id=request_id, data={"error": str(exc)}),
        )
        logger.error("Upstream request failed for %s: %s", request_id, exc)
        return JSONResponse({"error": f"Upstream request failed: {exc}"}, status_code=502)

    duration_ms = int((time.monotonic() - start_time) * 1000)

    try:
        response_body: dict[str, Any] = resp.json()
        response_body_str = json.dumps(response_body)
    except Exception:
        response_body = {}
        response_body_str = resp.text

    prompt_tokens, completion_tokens = handler.extract_usage(response_body)

    from prompt_engineering_proxy.realtime.events import REQUEST_COMPLETED

    await repo.update(
        request_id,
        response_status=resp.status_code,
        response_headers=json.dumps(dict(resp.headers)),
        response_body=response_body_str,
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    await publisher.publish(
        CHANNEL_REQUESTS,
        ProxyEvent(type=REQUEST_COMPLETED, request_id=request_id, data={"status": resp.status_code}),
    )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items() if k.lower() not in _HOP_BY_HOP},
        media_type=resp.headers.get("content-type"),
    )


async def _handle_streaming(
    http_client: httpx.AsyncClient,
    upstream_url: str,
    forward_headers: dict[str, str],
    body_bytes: bytes,
    publisher: RedisPublisher,
    request_id: str,
    repo: RequestRepository,
    handler: ProtocolHandler,
    start_time: float,
) -> Response:
    upstream_request = http_client.build_request(
        method="POST",
        url=upstream_url,
        headers=forward_headers,
        content=body_bytes,
    )
    try:
        upstream_response = await http_client.send(upstream_request, stream=True)
    except httpx.RequestError as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        await repo.update(request_id, error=str(exc), duration_ms=duration_ms)
        await publisher.publish(
            CHANNEL_REQUESTS,
            ProxyEvent(type=REQUEST_ERROR, request_id=request_id, data={"error": str(exc)}),
        )
        logger.error("Upstream stream request failed for %s: %s", request_id, exc)
        return JSONResponse({"error": f"Upstream request failed: {exc}"}, status_code=502)

    stream = tee_sse_stream(
        upstream_response=upstream_response,
        publisher=publisher,
        request_id=request_id,
        repo=repo,
        handler=handler,
        start_time=start_time,
    )

    return StreamingResponse(
        stream,
        status_code=upstream_response.status_code,
        headers={k: v for k, v in upstream_response.headers.items() if k.lower() not in _HOP_BY_HOP},
        media_type="text/event-stream",
    )
