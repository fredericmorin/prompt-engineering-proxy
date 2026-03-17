"""SSE endpoints — bridge Redis pub/sub channels to HTTP streaming responses."""

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from prompt_engineering_proxy.settings import settings
from prompt_engineering_proxy.realtime.events import CHANNEL_REQUESTS, CHANNEL_STREAM_PREFIX
from prompt_engineering_proxy.realtime.subscriber import RedisSubscriber
from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.services import RequestService

router = APIRouter()
logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


async def _stream_channel(redis_url: str, channel: str, disconnect: asyncio.Event) -> AsyncGenerator[str, None]:
    """Yield SSE strings from a Redis channel until the client disconnects."""
    subscriber = RedisSubscriber()
    async for sse_line in subscriber.subscribe(redis_url, channel):
        if disconnect.is_set():
            break
        yield sse_line


@router.get("/events")
async def sse_events(request: Request) -> StreamingResponse:
    """SSE stream of lifecycle events from the proxy:requests Redis channel."""
    disconnect = asyncio.Event()

    async def generator() -> AsyncGenerator[str, None]:
        async for chunk in _stream_channel(settings.REDIS_URL, CHANNEL_REQUESTS, disconnect):
            if await request.is_disconnected():
                disconnect.set()
                break
            yield chunk

    return StreamingResponse(generator(), headers=SSE_HEADERS)


@router.get("/requests/{request_id}/stream")
async def sse_request_stream(request: Request, request_id: str) -> StreamingResponse:
    """SSE stream of token chunks for a specific request.

    If the request is already complete, emits a synthetic 'done' event immediately.
    Otherwise subscribes to the proxy:stream:{id} Redis channel.
    """
    db: Database = request.app.state.db
    repo = RequestService(db)
    row = await repo.get(request_id)

    async def already_done() -> AsyncGenerator[str, None]:
        import json

        yield f"data: {json.dumps({'type': 'done', 'request_id': request_id})}\n\n"

    if row and row.response_body is not None:
        return StreamingResponse(already_done(), headers=SSE_HEADERS)

    channel = f"{CHANNEL_STREAM_PREFIX}{request_id}"
    disconnect = asyncio.Event()

    async def generator() -> AsyncGenerator[str, None]:
        import json

        async for chunk in _stream_channel(settings.REDIS_URL, channel, disconnect):
            if await request.is_disconnected():
                disconnect.set()
                break
            yield chunk
            # Detect [DONE] sentinel or a "stopped" event and close the stream
            try:
                payload = json.loads(chunk.removeprefix("data: ").strip())
                if isinstance(payload, dict):
                    chunk_type = payload.get("type")
                    if payload.get("data", {}).get("chunk") == "[DONE]":
                        yield f"data: {json.dumps({'type': 'done', 'request_id': request_id})}\n\n"
                        break
                    if chunk_type == "stopped":
                        # Already forwarded above; just stop iterating
                        break
            except Exception:
                pass

    return StreamingResponse(generator(), headers=SSE_HEADERS)
