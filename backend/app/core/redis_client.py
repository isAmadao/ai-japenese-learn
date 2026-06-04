"""Redis client — async for FastAPI lifespan, sync fallback for agent caching."""

import json
import logging
from typing import Any, Optional

import redis as sync_redis

logger = logging.getLogger(__name__)

# Try async redis first; fall back gracefully
try:
    import redis.asyncio as aioredis
    HAS_ASYNC_REDIS = True
except ImportError:
    aioredis = None
    HAS_ASYNC_REDIS = False
    logger.warning("redis.asyncio not available — using sync redis only")


class RedisClient:
    """Redis wrapper — async for startup/shutdown, sync for agent cache.

    Because the agent layer runs synchronously (SQLAlchemy sync sessions),
    we maintain a separate sync connection for cache get/set.
    """

    def __init__(self):
        self._async_client: Optional[aioredis.Redis] = None
        self._sync_pool: Optional[sync_redis.ConnectionPool] = None

    # ── Sync client (used by agents / non-async code) ────────

    @property
    def _sync(self) -> sync_redis.Redis:
        if self._sync_pool is None:
            from app.core.config import settings
            self._sync_pool = sync_redis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
        return sync_redis.Redis(connection_pool=self._sync_pool)

    def _sync_get(self, key: str) -> Optional[str]:
        try:
            val = self._sync.get(key)
            return str(val) if val is not None else None
        except Exception as e:
            logger.debug(f"Redis sync get failed: {e}")
            return None

    def _sync_set(self, key: str, value: str, ttl: int = 300):
        try:
            self._sync.setex(key, ttl, value)
        except Exception as e:
            logger.debug(f"Redis sync set failed: {e}")

    def _sync_delete(self, key: str):
        try:
            self._sync.delete(key)
        except Exception as e:
            logger.debug(f"Redis sync delete failed: {e}")

    # ── Async client (used by lifespan / future async routes) ─

    @property
    def client(self):
        if self._async_client is None:
            raise RuntimeError("Async redis not connected.")
        return self._async_client

    async def connect(self):
        if not HAS_ASYNC_REDIS:
            logger.info("redis.asyncio not installed — sync cache still available")
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
            logger.info("Redis connected (async)")
        except Exception as e:
            logger.warning(f"Async Redis connection failed: {e}")
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
