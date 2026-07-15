"""Redis client — with automatic in-memory fallback when Redis is unavailable.

When Redis is down (or not configured), cache operations degrade gracefully
to a TTL-aware local dict so the application still gets session caching
and LLM response caching without any code changes.
"""

import json
import logging
import time
from typing import Any, Optional

import redis as sync_redis

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    HAS_ASYNC_REDIS = True
except ImportError:
    aioredis = None
    HAS_ASYNC_REDIS = False


class _LocalCache:
    """TTL-aware in-memory cache — drop-in when Redis is unavailable."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._expiry: dict[str, float] = {}

    def get(self, key: str) -> Optional[str]:
        val = self._store.get(key)
        if val is None:
            return None
        # Check TTL
        expiry = self._expiry.get(key)
        if expiry is not None and time.time() > expiry:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return None
        return val

    def set(self, key: str, value: str, ttl: int = 300):
        self._store[key] = value
        self._expiry[key] = time.time() + ttl

    def delete(self, key: str):
        self._store.pop(key, None)
        self._expiry.pop(key, None)

    @property
    def available(self) -> bool:
        return True


class RedisClient:
    """Redis wrapper — async for startup/shutdown, sync for agent cache.

    Automatically falls back to in-memory cache when Redis connection fails,
    so the application remains fully functional without a Redis server.
    """

    def __init__(self):
        self._async_client: Optional[aioredis.Redis] = None
        self._sync_pool: Optional[sync_redis.ConnectionPool] = None
        self._local = _LocalCache()

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
                socket_connect_timeout=1,  # fail fast when Redis is down
            )
        return sync_redis.Redis(connection_pool=self._sync_pool)

    def _sync_get(self, key: str) -> Optional[str]:
        if self._async_client is None:
            return self._local.get(key)
        try:
            val = self._sync.get(key)
            return str(val) if val is not None else None
        except Exception:
            return self._local.get(key)

    def _sync_set(self, key: str, value: str, ttl: int = 300):
        if self._async_client is None:
            self._local.set(key, value, ttl)
            return
        try:
            self._sync.setex(key, ttl, value)
        except Exception:
            self._local.set(key, value, ttl)

    def _sync_delete(self, key: str):
        if self._async_client is None:
            self._local.delete(key)
            return
        try:
            self._sync.delete(key)
        except Exception:
            self._local.delete(key)

    def _sync_llen(self, key: str) -> int:
        """List length. Returns 0 if Redis unavailable."""
        try:
            return self._sync.llen(key)
        except Exception:
            return 0

    def _sync_lpop(self, key: str, count: int = 1) -> list:
        """Pop *count* items from list head. Returns [] if unavailable."""
        try:
            result = self._sync.lpop(key, count=count)
            return result if result else []
        except Exception:
            return []

    def _sync_rpush(self, key: str, value: str):
        """Push value to list tail."""
        try:
            self._sync.rpush(key, value)
        except Exception:
            pass

    # ── Async client (used by lifespan / future async routes) ─

    @property
    def client(self):
        if self._async_client is None:
            raise RuntimeError("Async redis not connected.")
        return self._async_client

    async def connect(self):
        self._local = _LocalCache()  # fresh cache on restart
        if not HAS_ASYNC_REDIS:
            logger.info("Local cache active (redis.asyncio not installed)")
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
            logger.warning(f"Redis unavailable ({e}) — using local cache")
            self._async_client = None

    async def disconnect(self):
        if self._async_client:
            await self._async_client.close()
            self._async_client = None
        # Keep local cache alive across lifespan (it's in-process)

    async def get(self, key: str) -> Optional[str]:
        if self._async_client:
            try:
                return await self._async_client.get(key)
            except Exception:
                pass
        return self._local.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300):
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        if self._async_client:
            try:
                await self._async_client.setex(key, ttl, value)
                return
            except Exception:
                pass
        self._local.set(key, value, ttl)

    async def delete(self, key: str):
        if self._async_client:
            try:
                await self._async_client.delete(key)
            except Exception:
                pass
        self._local.delete(key)


redis_client = RedisClient()
