"""Redis 封装：API 缓存 / 限流 / 画像热点。"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


def _key(prefix: str, *parts: str) -> str:
    h = hashlib.md5(":".join(parts).encode()).hexdigest()
    return f"{prefix}:{h}"


async def cache_get(key_prefix: str, *parts: str) -> Any | None:
    r = get_redis()
    raw = await r.get(_key(key_prefix, *parts))
    return json.loads(raw) if raw else None


async def cache_set(key_prefix: str, *parts: str, value: Any, ttl: int = 21600) -> None:
    r = get_redis()
    await r.setex(_key(key_prefix, *parts), ttl, json.dumps(value, default=str))


async def cache_fallback(key_prefix: str, *parts: str) -> Any | None:
    """配额超限时的降级读取，无视 TTL 兜底。"""
    r = get_redis()
    raw = await r.get(_key(key_prefix, *parts))
    return json.loads(raw) if raw else None
