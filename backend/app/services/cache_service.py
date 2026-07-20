import asyncio
import json
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

CATALOG_CACHE_VERSION = "v2"
CATALOG_CACHE_TTL_SECONDS = 60
CATALOG_LOCK_TTL_SECONDS = 5
LEGACY_CATALOG_CACHE_KEY = "cache:products:all"

T = TypeVar("T")


def namespaced_key(component: str, *, version: str = "v1") -> str:
    clean_component = component.strip().strip(":")
    return f"{settings.cache_namespace}:{version}:{clean_component}"


CATALOG_CACHE_KEY = namespaced_key("catalog:products", version=CATALOG_CACHE_VERSION)
CATALOG_LOCK_KEY = f"{CATALOG_CACHE_KEY}:fill-lock"


@dataclass(frozen=True)
class CacheRead:
    available: bool
    hit: bool
    value: Any = None


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    count: int | None
    backend_available: bool


async def read_json(key: str) -> CacheRead:
    try:
        raw_value = await redis_client.get(key)
    except RedisError as exc:
        logger.warning("Cache read failed for %s: %s", key, type(exc).__name__)
        return CacheRead(available=False, hit=False)

    if raw_value is None:
        return CacheRead(available=True, hit=False)

    try:
        return CacheRead(available=True, hit=True, value=json.loads(raw_value))
    except (TypeError, json.JSONDecodeError):
        logger.warning("Corrupt JSON cache entry removed for %s", key)
        await delete_keys(key)
        return CacheRead(available=True, hit=False)


async def write_json(key: str, value: Any, ttl_seconds: int) -> bool:
    try:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        await redis_client.setex(key, max(1, int(ttl_seconds)), payload)
        return True
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("Cache write failed for %s: %s", key, type(exc).__name__)
        return False


async def delete_keys(*keys: str) -> bool:
    if not keys:
        return True
    try:
        await redis_client.delete(*keys)
        return True
    except RedisError as exc:
        logger.warning("Cache delete failed for %s: %s", ",".join(keys), type(exc).__name__)
        return False


async def invalidate_catalog_cache() -> bool:
    """Invalidate current and legacy keys without failing a committed DB mutation."""
    return await delete_keys(CATALOG_CACHE_KEY, CATALOG_LOCK_KEY, LEGACY_CATALOG_CACHE_KEY)


async def _try_catalog_lock(token: str) -> bool | None:
    try:
        return bool(
            await redis_client.set(
                CATALOG_LOCK_KEY,
                token,
                nx=True,
                ex=CATALOG_LOCK_TTL_SECONDS,
            )
        )
    except RedisError as exc:
        logger.warning("Catalog fill lock unavailable: %s", type(exc).__name__)
        return None


async def _release_catalog_lock(token: str) -> None:
    script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    try:
        await redis_client.eval(script, 1, CATALOG_LOCK_KEY, token)
    except RedisError as exc:
        logger.warning("Catalog fill lock release failed: %s", type(exc).__name__)


async def load_catalog_cached(loader: Callable[[], Awaitable[T]]) -> T:
    cached = await read_json(CATALOG_CACHE_KEY)
    if cached.hit:
        return cached.value

    token = secrets.token_urlsafe(18)
    lock_acquired = await _try_catalog_lock(token)
    if lock_acquired is None:
        return await loader()

    if not lock_acquired:
        for _ in range(20):
            await asyncio.sleep(0.05)
            cached = await read_json(CATALOG_CACHE_KEY)
            if cached.hit:
                return cached.value
            if not cached.available:
                return await loader()

        # A slow or failed lock owner must not make catalog requests hang.
        return await loader()

    try:
        cached = await read_json(CATALOG_CACHE_KEY)
        if cached.hit:
            return cached.value
        value = await loader()
        await write_json(CATALOG_CACHE_KEY, value, CATALOG_CACHE_TTL_SECONDS)
        return value
    finally:
        await _release_catalog_lock(token)


async def check_rate_limit(
    scope: str,
    identity: str,
    *,
    limit: int,
    window_seconds: int,
) -> RateLimitDecision:
    key = namespaced_key(f"rate-limit:{scope}:{identity}")
    script = (
        "local count = redis.call('incr', KEYS[1]); "
        "if count == 1 then redis.call('expire', KEYS[1], ARGV[1]); end; "
        "return count"
    )
    try:
        count = int(await redis_client.eval(script, 1, key, max(1, window_seconds)))
    except RedisError as exc:
        # Catalog reads remain available from PostgreSQL during a cache outage.
        logger.warning("Rate-limit backend unavailable for %s: %s", scope, type(exc).__name__)
        return RateLimitDecision(allowed=True, count=None, backend_available=False)
    return RateLimitDecision(allowed=count <= limit, count=count, backend_available=True)


async def redis_health() -> tuple[bool, str]:
    try:
        pong = await redis_client.ping()
    except RedisError as exc:
        return False, type(exc).__name__
    return bool(pong), "ok" if pong else "unexpected_response"
