"""
Unit tests for the Redis cache helper.

These tests do not require a running Redis instance. We inject a tiny in-memory async fake
client that implements the subset of commands the cache layer uses.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import TypeAdapter

from app.core import cache


class _FakePipeline:
    def __init__(self, client: "_FakeRedis") -> None:
        self._client = client
        self._ops: list[tuple[str, str]] = []

    def incr(self, key: str) -> "_FakePipeline":
        self._ops.append(("incr", key))
        return self

    async def execute(self) -> list[int]:
        results: list[int] = []
        for op, key in self._ops:
            if op == "incr":
                results.append(await self._client.incr(key))
        return results


class _FakeRedis:
    """
    Minimal async Redis client used for tests.

    Stores values as bytes and supports only the commands our cache layer uses.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)

    async def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    async def set(self, key: str, value: bytes, ex: int | None = None) -> bool:
        # TTL is intentionally ignored for unit tests.
        self._store[key] = value
        return True

    async def mget(self, keys: tuple[str, str]) -> list[bytes | None]:
        return [self._store.get(keys[0]), self._store.get(keys[1])]

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, b"0").decode("utf-8"))
        current += 1
        self._store[key] = str(current).encode("utf-8")
        return current

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    """
    Install an in-memory Redis client and clear any previous inflight state.
    """
    fake = _FakeRedis()
    monkeypatch.setattr(cache, "_redis_client", fake, raising=False)
    cache._inflight.clear()
    return fake


@pytest.mark.asyncio
async def test_cached_json_coalesces_inflight(fake_redis: _FakeRedis) -> None:
    calls = 0

    async def loader() -> dict[str, int]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"value": 123}

    adapter = TypeAdapter(dict[str, int])

    results = await asyncio.gather(
        *[
            cache.cached_json("key:1", loader=loader, adapter=adapter, ttl_seconds=60)
            for _ in range(10)
        ]
    )

    assert calls == 1
    assert results == [{"value": 123}] * 10

    # Second read should be a cache hit and not invoke loader again.
    calls = 0
    hit = await cache.cached_json("key:1", loader=loader, adapter=adapter, ttl_seconds=60)
    assert calls == 0
    assert hit == {"value": 123}


@pytest.mark.asyncio
async def test_bump_versions_and_get_versions(fake_redis: _FakeRedis) -> None:
    # Default versions are 0 when keys do not exist.
    assert await cache.get_versions("user-1", "bpm") == (0, 0)

    await cache.bump_versions("user-1", "bpm")
    assert await cache.get_versions("user-1", "bpm") == (1, 1)

    # Bumping a different type should increment the user-wide version as well.
    await cache.bump_versions("user-1", "spo2")
    assert (await cache.get_versions("user-1", "bpm"))[0] == 2
    assert await cache.get_versions("user-1", "spo2") == (2, 1)

    # When no type is requested, only the user-wide version is returned.
    assert await cache.get_versions("user-1", None) == (2, 0)


@pytest.mark.asyncio
async def test_cached_json_falls_back_when_cache_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "_redis_client", None, raising=False)

    called: list[Any] = []

    async def loader() -> int:
        called.append(True)
        return 7

    adapter = TypeAdapter(int)
    value = await cache.cached_json("key:missing", loader=loader, adapter=adapter)

    assert value == 7
    assert called == [True]
