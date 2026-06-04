"""Redis client for caching and session management.

Usage (future):
    from app.core.redis_client import redis_client
    await redis_client.set("key", "value")
    val = await redis_client.get("key")
"""

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings


class RedisClient:
    """Thin wrapper around redis for caching & rate-limiting."""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    async def connect(self):
        self._client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        await self._client.ping()

    async def disconnect(self):
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300):
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        await self.client.setex(key, ttl, value)

    async def delete(self, key: str):
        await self.client.delete(key)


redis_client = RedisClient()
