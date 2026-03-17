"""SSE stream tee — forward raw bytes to the client while publishing chunks to Redis
and assembling the full response for SQLite storage on completion."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

import httpx

from prompt_engineering_proxy.proxy.protocols.base import ProtocolHandler
from prompt_engineering_proxy.realtime.events import (
    CHANNEL_REQUESTS,
    CHANNEL_STREAM_PREFIX,
    REQUEST_COMPLETED,
    REQUEST_STOPPED,
    STREAM_CHUNK,
    ProxyEvent,
)
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.services import RequestService

logger = logging.getLogger(__name__)


async def tee_ndjson_stream(
    upstream_response: httpx.Response,
    publisher: RedisPublisher,
    request_id: str,
    repo: RequestService,
    handler: ProtocolHandler,
    start_time: float,
    cancel_event: asyncio.Event | None = None,
) -> AsyncGenerator[bytes, None]:
    """Async generator that tees an NDJSON stream (used by Ollama):
    - Yields raw bytes to the client (transparent pass-through)
    - Parses each newline-delimited JSON chunk and publishes to Redis
    - On completion, assembles the full response and stores it in SQLite
    - Stops early if cancel_event is set
    """
    buffer = ""
    data_lines: list[str] = []
    ttfb_ms: list[int | None] = [None]
    stopped = False

    try:
        async for raw_chunk in upstream_response.aiter_bytes():
            if cancel_event and cancel_event.is_set():
                stopped = True
                break

            if ttfb_ms[0] is None and raw_chunk:
                ttfb_ms[0] = int((time.monotonic() - start_time) * 1000)

            yield raw_chunk

            buffer += raw_chunk.decode("utf-8", errors="replace")

            # Process complete newline-delimited JSON lines
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                data_lines.append(line)
                try:
                    await publisher.publish(
                        f"{CHANNEL_STREAM_PREFIX}{request_id}",
                        ProxyEvent(
                            type=STREAM_CHUNK,
                            request_id=request_id,
                            data={"chunk": line},
                        ),
                    )
                except Exception:
                    logger.debug("Failed to publish NDJSON chunk for request %s", request_id)

    except Exception as exc:
        logger.error("NDJSON stream error for request %s: %s", request_id, exc)
        raise
    finally:
        await upstream_response.aclose()
        await _finalize_stream(
            repo=repo,
            publisher=publisher,
            request_id=request_id,
            handler=handler,
            status_code=upstream_response.status_code,
            response_headers=dict(upstream_response.headers),
            data_lines=data_lines,
            start_time=start_time,
            ttfb_ms=ttfb_ms[0],
            stopped=stopped,
        )


async def tee_sse_stream(
    upstream_response: httpx.Response,
    publisher: RedisPublisher,
    request_id: str,
    repo: RequestService,
    handler: ProtocolHandler,
    start_time: float,
    cancel_event: asyncio.Event | None = None,
) -> AsyncGenerator[bytes, None]:
    """Async generator that tees an SSE stream:
    - Yields raw bytes to the client (transparent pass-through)
    - Parses SSE events and publishes each data chunk to Redis
    - On completion, assembles the full response and stores it in SQLite
    - Stops early if cancel_event is set
    """
    buffer = ""
    data_lines: list[str] = []
    ttfb_ms: list[int | None] = [None]
    stopped = False

    try:
        async for raw_chunk in upstream_response.aiter_bytes():
            if cancel_event and cancel_event.is_set():
                stopped = True
                break

            if ttfb_ms[0] is None and raw_chunk:
                ttfb_ms[0] = int((time.monotonic() - start_time) * 1000)

            # Forward to client immediately (transparent pass-through)
            yield raw_chunk

            # Accumulate text for SSE event boundary detection
            buffer += raw_chunk.decode("utf-8", errors="replace")

            # Process complete SSE events (each terminated by \n\n)
            while "\n\n" in buffer:
                event_text, buffer = buffer.split("\n\n", 1)
                for line in event_text.strip().split("\n"):
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    data_lines.append(data)
                    try:
                        await publisher.publish(
                            f"{CHANNEL_STREAM_PREFIX}{request_id}",
                            ProxyEvent(
                                type=STREAM_CHUNK,
                                request_id=request_id,
                                data={"chunk": data},
                            ),
                        )
                    except Exception:
                        logger.debug("Failed to publish stream chunk for request %s", request_id)

    except Exception as exc:
        logger.error("Stream error for request %s: %s", request_id, exc)
        raise
    finally:
        await upstream_response.aclose()
        await _finalize_stream(
            repo=repo,
            publisher=publisher,
            request_id=request_id,
            handler=handler,
            status_code=upstream_response.status_code,
            response_headers=dict(upstream_response.headers),
            data_lines=data_lines,
            start_time=start_time,
            ttfb_ms=ttfb_ms[0],
            stopped=stopped,
        )


async def _finalize_stream(
    repo: RequestService,
    publisher: RedisPublisher,
    request_id: str,
    handler: ProtocolHandler,
    status_code: int,
    response_headers: dict[str, str],
    data_lines: list[str],
    start_time: float,
    ttfb_ms: int | None,
    stopped: bool = False,
) -> None:
    """Store the assembled response and publish the completion event."""
    duration_ms = int((time.monotonic() - start_time) * 1000)

    parsed: list[dict[str, object]] = []
    for data in data_lines:
        if data == "[DONE]":
            continue
        try:
            obj = json.loads(data)
            if isinstance(obj, dict):
                parsed.append(obj)
        except json.JSONDecodeError:
            pass

    assembled = handler.assemble_streaming_response(parsed)
    prompt_tokens, completion_tokens = handler.extract_usage(assembled)

    event_type = REQUEST_STOPPED if stopped else REQUEST_COMPLETED

    try:
        await repo.update(
            request_id,
            response_status=status_code,
            response_headers=json.dumps(response_headers),
            response_body=json.dumps(assembled),
            duration_ms=duration_ms,
            ttfb_ms=ttfb_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        await publisher.publish(
            CHANNEL_REQUESTS,
            ProxyEvent(
                type=event_type,
                request_id=request_id,
                data={"status": status_code, "stopped": stopped},
            ),
        )
        # Also publish a done sentinel on the stream channel so the frontend SSE closes
        if stopped:
            await publisher.publish(
                f"{CHANNEL_STREAM_PREFIX}{request_id}",
                ProxyEvent(
                    type="stopped",
                    request_id=request_id,
                ),
            )
    except Exception as exc:
        logger.error("Failed to finalize stream for request %s: %s", request_id, exc)
