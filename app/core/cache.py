"""
Lightweight Redis cache helpers.

Design goals:
- Best-effort: if Redis is down or the dependency isn't installed, fall back to DB-only reads.
- Coalescing: concurrent identical requests share one in-flight DB query ("singleflight").
- Invalidation: writes bump small version counters so read keys become automatically stale.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeVar

import structlog
from pydantic import TypeAdapter

from app.core.config import settings

logger = structlog.get_logger(__name__)

T = TypeVar("T")

try:  # pragma: no cover - import is validated in environments that install redis
    import redis.asyncio as redis
except ModuleNotFoundError:  # pragma: no cover
    redis = None  # type: ignore[assignment]

if TYPE_CHECKING:
    import redis.asyncio as redis_typing

    RedisClient = redis_typing.Redis
else:
    RedisClient = Any

_redis_client: RedisClient | None = None
# One task per cache key to prevent stampedes when many clients request the same data.
_inflight: dict[str, asyncio.Task[T]] = {}
_inflight_lock = asyncio.Lock()

# Keep TTL small to reduce staleness risk.
DEFAULT_CACHE_TTL_SECONDS = settings.VITALS_CACHE_TTL_SECONDS


async def init_cache() -> RedisClient | None:
    """Create a singleton Redis client; degrade gracefully if unavailable."""
    global _redis_client

    if not settings.REDIS_URL:
        return None

    if redis is None:
        logger.warning("cache_dependency_missing", dependency="redis")
        return None

    client = redis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        await client.ping()
    except Exception as exc:  # pragma: no cover - best-effort init
        logger.warning("cache_ping_failed", error=str(exc), url=settings.REDIS_URL)
        return None

    _redis_client = client
    return client


async def close_cache() -> None:
    """Close the Redis client on shutdown."""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None


def get_cache_client() -> RedisClient | None:
    """Expose the shared Redis client."""
    return _redis_client


def _version_key(user_id: str, type_label: str | None = None) -> str:
    if type_label:
        return f"vitals:version:{user_id}:{type_label}"
    return f"vitals:version:{user_id}"


async def bump_versions(user_id: str, type_label: str | None = None) -> None:
    """
    Invalidate cached vitals by incrementing user-wide and type-specific versions.

    We do not delete cached response keys directly. Instead, response keys include the current
    version numbers, so after a bump subsequent reads will compute a different key and miss
    until it is repopulated.
    """
    client = _redis_client
    if client is None:
        return

    try:
        pipeline = client.pipeline()
        pipeline.incr(_version_key(user_id))
        if type_label:
            pipeline.incr(_version_key(user_id, type_label))
        await pipeline.execute()
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.warning("cache_invalidate_failed", error=str(exc))


async def get_versions(user_id: str, type_label: str | None = None) -> tuple[int, int]:
    """
    Fetch the user-level and type-level version counters.
    """
    client = _redis_client
    if client is None:
        return (0, 0)

    if type_label is None:
        try:
            user_value = await client.get(_version_key(user_id))
        except Exception as exc:  # pragma: no cover - cache is best-effort
            logger.warning("cache_version_read_failed", error=str(exc))
            return (0, 0)
        return (int(user_value) if user_value is not None else 0, 0)

    keys = (_version_key(user_id), _version_key(user_id, type_label))
    try:
        values = await client.mget(keys)
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.warning("cache_version_read_failed", error=str(exc))
        return (0, 0)

    return tuple(int(value) if value is not None else 0 for value in values)


async def cached_json(
    key: str,
    loader: Callable[[], Awaitable[T]],
    adapter: TypeAdapter[T],
    ttl_seconds: int | None = None,
) -> T:
    """
    Get a cached value if present; otherwise execute loader once per key and cache the result.

    Notes:
    - `adapter` controls how values are serialized/deserialized.
    - Cache failures never fail the request: we return fresh data from `loader()` instead.
    """
    client = _redis_client
    if client is None:
        return await loader()

    cached = await _read_from_cache(client, key, adapter)
    if cached is not None:
        return cached

    async with _inflight_lock:
        task = _inflight.get(key)
        if task is None:
            task = asyncio.create_task(
                _fetch_and_store(client, key, loader, adapter, ttl_seconds)
            )
            _inflight[key] = task

    try:
        return await task
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def _read_from_cache(
    client: RedisClient, key: str, adapter: TypeAdapter[T]
) -> T | None:
    try:
        raw = await client.get(key)
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.warning("cache_read_failed", key=key, error=str(exc))
        return None

    if raw is None:
        return None

    try:
        return adapter.validate_json(raw)
    except Exception as exc:
        logger.warning("cache_deserialize_failed", key=key, error=str(exc))
        await _safe_delete(client, key)
        return None


async def _fetch_and_store(
    client: RedisClient,
    key: str,
    loader: Callable[[], Awaitable[T]],
    adapter: TypeAdapter[T],
    ttl_seconds: int | None,
) -> T:
    result = await loader()
    ttl = ttl_seconds or DEFAULT_CACHE_TTL_SECONDS

    try:
        await client.set(key, adapter.dump_json(result), ex=ttl)
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.warning("cache_write_failed", key=key, error=str(exc))

    return result


async def _safe_delete(client: RedisClient, key: str) -> None:
    try:
        await client.delete(key)
    except Exception:  # pragma: no cover - cache is best-effort
        return
