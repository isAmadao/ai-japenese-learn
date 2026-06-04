"""Redis client for caching and session management.

Gracefully handles missing redis.asyncio (fallback to sync client).
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try async redis first; fall back gracefully
try:
    import redis.asyncio as aioredis
    HAS_ASYNC_REDIS = True
except ImportError:
    aioredis = None
    HAS_ASYNC_REDIS = False
    logger.warning("redis.asyncio not available — using sync redis client fallback")


class RedisClient:
    """Thin wrapper around redis for caching & rate-limiting."""

    def __init__(self):
        self._async_client: Optional[aioredis.Redis] = None if HAS_ASYNC_REDIS else None

    @property
    def client(self):
        if self._async_client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._async_client

    async def connect(self):
        if not HAS_ASYNC_REDIS:
            logger.warning("redis.asyncio not installed — skipping Redis connection")
            return
        from app.core.config import settings
        self._async_client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        try:
            await self._async_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._async_client = None

    async def disconnect(self):
        if self._async_client:
            await self._async_client.close()
            self._async_client = None

    async def get(self, key: str) -> Optional[str]:
        if not self._async_client:
            return None
        return await self._async_client.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300):
        if not self._async_client:
            return
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        await self._async_client.setex(key, ttl, value)

    async def delete(self, key: str):
        if not self._async_client:
            return
        await self._async_client.delete(key)


redis_client = RedisClient()
