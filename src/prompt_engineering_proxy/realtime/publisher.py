import json
import logging
from typing import Any

import redis.asyncio as aioredis

from prompt_engineering_proxy.realtime.events import ProxyEvent

logger = logging.getLogger(__name__)


class RedisPublisher:
    def __init__(self) -> None:
        self._redis: aioredis.Redis[Any] | None = None

    async def connect(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        # Test the connection
        await self._redis.ping()  # type: ignore[misc]
        logger.info("Redis publisher connected")

    async def publish(self, channel: str, event: ProxyEvent) -> None:
        if not self._redis:
            logger.debug("Redis not connected, skipping publish to %s", channel)
            return
        payload = json.dumps(event.model_dump())
        await self._redis.publish(channel, payload)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("Redis publisher closed")

    async def ping(self) -> bool:
        try:
            if not self._redis:
                return False
            return bool(await self._redis.ping())
        except Exception:
            return False
