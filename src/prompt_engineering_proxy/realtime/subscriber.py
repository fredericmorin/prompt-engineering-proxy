"""Redis pub/sub subscriber — yields SSE-formatted events for HTTP streaming."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisSubscriber:
    """Subscribe to a Redis channel and yield SSE-formatted strings.

    Creates a dedicated Redis connection per subscriber instance so that
    pub/sub state is isolated from the shared publisher connection.
    """

    async def subscribe(self, redis_url: str, channel: str) -> AsyncGenerator[str, None]:
        redis: aioredis.Redis[Any] = aioredis.from_url(redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        logger.debug("Subscribed to Redis channel: %s", channel)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is not None and message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
        except Exception as exc:
            logger.debug("Redis subscriber error on channel %s: %s", channel, exc)
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                pass
            await redis.aclose()
            logger.debug("Unsubscribed from Redis channel: %s", channel)
