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
    Otherwise replays any buffered chunks (to avoid losing early tokens due to the
    race between chunk publication and subscriber connection), then subscribes to
    the proxy:stream:{id} Redis channel for the remainder.
    """
    import json

    db: Database = request.app.state.db
    repo = RequestService(db)
    row = await repo.get(request_id)

    async def already_done() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'done', 'request_id': request_id})}\n\n"

    if row and row.response_body is not None:
        return StreamingResponse(already_done(), headers=SSE_HEADERS)

    channel = f"{CHANNEL_STREAM_PREFIX}{request_id}"
    disconnect = asyncio.Event()

    # Get the in-memory chunk buffer (populated by the background streaming task).
    chunk_buffers: dict[str, list[str]] = getattr(request.app.state, "stream_chunk_buffers", {})
    chunk_buffer: list[str] | None = chunk_buffers.get(request_id)

    def _is_terminal(chunk: str) -> str | None:
        """Return 'done' or 'stopped' if this chunk signals end-of-stream, else None."""
        try:
            payload = json.loads(chunk.removeprefix("data: ").strip())
            if isinstance(payload, dict):
                if payload.get("data", {}).get("chunk") == "[DONE]":
                    return "done"
                if payload.get("type") == "stopped":
                    return "stopped"
        except Exception:
            pass
        return None

    async def generator() -> AsyncGenerator[str, None]:
        import redis.asyncio as aioredis
        from typing import Any

        # 1. Subscribe to Redis EAGERLY so no new messages are missed while
        #    we replay the buffer.  We must await pubsub.subscribe() before
        #    snapshotting the buffer — otherwise chunks published during replay
        #    would be lost by both the snapshot and the (not-yet-active) subscriber.
        redis_conn: aioredis.Redis[Any] = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_conn.pubsub()
        await pubsub.subscribe(channel)

        try:
            # 2. Replay buffered chunks (published before we subscribed).
            replayed_count = 0
            if chunk_buffer is not None:
                snapshot = list(chunk_buffer)
                replayed_count = len(snapshot)
                for buffered in snapshot:
                    if await request.is_disconnected():
                        disconnect.set()
                        return
                    sse_line = f"data: {buffered}\n\n"
                    yield sse_line
                    terminal = _is_terminal(sse_line)
                    if terminal == "done":
                        yield f"data: {json.dumps({'type': 'done', 'request_id': request_id})}\n\n"
                        return
                    if terminal == "stopped":
                        return

            # 3. Yield live chunks from Redis, skipping duplicates already replayed.
            skipped = 0
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                if disconnect.is_set() or await request.is_disconnected():
                    disconnect.set()
                    break
                # Skip chunks that were already replayed from the buffer.
                if skipped < replayed_count:
                    skipped += 1
                    continue
                chunk = f"data: {message['data']}\n\n"
                yield chunk
                terminal = _is_terminal(chunk)
                if terminal == "done":
                    yield f"data: {json.dumps({'type': 'done', 'request_id': request_id})}\n\n"
                    break
                if terminal == "stopped":
                    break
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                pass
            await redis_conn.aclose()

    return StreamingResponse(generator(), headers=SSE_HEADERS)
