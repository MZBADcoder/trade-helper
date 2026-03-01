from __future__ import annotations

import asyncio
import threading

import pytest
import redis

import app.application.auth.login_throttle as login_throttle_module
import app.infrastructure.auth.login_throttle as infrastructure_login_throttle_module
from app.application.auth.login_throttle import AuthLoginThrottle
from app.domain.auth.constants import ERROR_AUTH_RATE_LIMITED
from app.infrastructure.auth.login_throttle import RedisAuthLoginThrottle


async def test_throttle_blocks_after_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    current = 100.0
    monkeypatch.setattr(login_throttle_module.time, "monotonic", lambda: current)

    throttle = AuthLoginThrottle(max_failures=2, window_seconds=60, block_seconds=120)
    await throttle.record_failure(key="trader@example.com")
    await throttle.assert_allowed(key="trader@example.com")

    await throttle.record_failure(key="trader@example.com")
    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        await throttle.assert_allowed(key="trader@example.com")


async def test_throttle_caps_entry_growth_and_purges_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    current = 0.0
    monkeypatch.setattr(login_throttle_module.time, "monotonic", lambda: current)

    throttle = AuthLoginThrottle(max_failures=5, window_seconds=10, block_seconds=30, max_entries=2)
    await throttle.record_failure(key="a@example.com")
    await throttle.record_failure(key="b@example.com")
    await throttle.record_failure(key="c@example.com")

    assert len(throttle._states) == 2
    assert "c@example.com" in throttle._states

    current = 20.0
    await throttle.assert_allowed(key="d@example.com")
    assert len(throttle._states) == 0


class FakeRedisClient:
    def __init__(self, now_provider) -> None:
        self._now_provider = now_provider
        self._values: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}

    async def get(self, key: str):
        self._purge_expired()
        return self._values.get(key)

    async def incr(self, key: str) -> int:
        self._purge_expired()
        value = int(self._values.get(key, "0")) + 1
        self._values[key] = str(value)
        return value

    async def ttl(self, key: str) -> int:
        self._purge_expired()
        if key not in self._values:
            return -2
        expire_at = self._expires_at.get(key)
        if expire_at is None:
            return -1
        return max(0, int(expire_at - self._now_provider()))

    async def expire(self, key: str, seconds: int) -> bool:
        self._purge_expired()
        if key not in self._values:
            return False
        self._expires_at[key] = self._now_provider() + seconds
        return True

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._values[key] = value
        if ex is not None:
            self._expires_at[key] = self._now_provider() + ex
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._values:
                deleted += 1
            self._values.pop(key, None)
            self._expires_at.pop(key, None)
        return deleted

    def _purge_expired(self) -> None:
        now = self._now_provider()
        expired = [key for key, expire_at in self._expires_at.items() if expire_at <= now]
        for key in expired:
            self._values.pop(key, None)
            self._expires_at.pop(key, None)


async def test_redis_throttle_blocks_across_shared_client() -> None:
    current = 100.0
    client = FakeRedisClient(now_provider=lambda: current)

    throttle_a = RedisAuthLoginThrottle(
        redis_url="redis://unused",
        max_failures=2,
        window_seconds=60,
        block_seconds=120,
        client=client,
        time_provider=lambda: current,
    )
    throttle_b = RedisAuthLoginThrottle(
        redis_url="redis://unused",
        max_failures=2,
        window_seconds=60,
        block_seconds=120,
        client=client,
        time_provider=lambda: current,
    )

    await throttle_a.record_failure(key="trader@example.com")
    await throttle_b.assert_allowed(key="trader@example.com")

    await throttle_b.record_failure(key="trader@example.com")
    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        await throttle_a.assert_allowed(key="trader@example.com")

    current = 300.0
    await throttle_b.assert_allowed(key="trader@example.com")


class BrokenRedisClient:
    async def get(self, key: str):
        raise redis.ConnectionError("redis unavailable")

    async def incr(self, key: str) -> int:
        raise redis.ConnectionError("redis unavailable")

    async def ttl(self, key: str) -> int:
        raise redis.ConnectionError("redis unavailable")

    async def expire(self, key: str, seconds: int) -> bool:
        raise redis.ConnectionError("redis unavailable")

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        raise redis.ConnectionError("redis unavailable")

    async def delete(self, *keys: str) -> int:
        raise redis.ConnectionError("redis unavailable")


async def test_redis_throttle_falls_back_to_in_memory_when_redis_fails() -> None:
    current = 100.0
    throttle = RedisAuthLoginThrottle(
        redis_url="redis://unused",
        max_failures=2,
        window_seconds=60,
        block_seconds=120,
        client=BrokenRedisClient(),
        time_provider=lambda: current,
    )

    await throttle.record_failure(key="trader@example.com")
    await throttle.assert_allowed(key="trader@example.com")

    await throttle.record_failure(key="trader@example.com")
    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        await throttle.assert_allowed(key="trader@example.com")


def test_redis_throttle_fallback_is_safe_across_event_loops() -> None:
    current = 100.0
    throttle = RedisAuthLoginThrottle(
        redis_url="redis://unused",
        max_failures=10,
        window_seconds=60,
        block_seconds=120,
        client=BrokenRedisClient(),
        time_provider=lambda: current,
    )
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def exercise(index: int) -> None:
        try:
            barrier.wait()
            asyncio.run(throttle.record_failure(key=f"trader{index}@example.com"))
            asyncio.run(throttle.assert_allowed(key=f"trader{index}@example.com"))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=exercise, args=(idx,)) for idx in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []


class ClosableRedisClient:
    def __init__(self) -> None:
        self.owner_loop_id = id(asyncio.get_running_loop())
        self.closed = False
        self.closed_loop_id: int | None = None

    async def get(self, key: str):
        return None

    async def aclose(self) -> None:
        self.closed_loop_id = id(asyncio.get_running_loop())
        self.closed = True


def test_redis_throttle_closes_ephemeral_clients_on_their_owner_loops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_clients: list[ClosableRedisClient] = []

    def build_client(*args, **kwargs) -> ClosableRedisClient:
        client = ClosableRedisClient()
        created_clients.append(client)
        return client

    monkeypatch.setattr(infrastructure_login_throttle_module.redis.Redis, "from_url", build_client)

    throttle = RedisAuthLoginThrottle(redis_url="redis://unused")
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def exercise() -> None:
        try:
            barrier.wait()
            asyncio.run(throttle.assert_allowed(key="trader@example.com"))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=exercise) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(created_clients) == 2
    assert all(client.closed for client in created_clients)
    assert all(client.closed_loop_id == client.owner_loop_id for client in created_clients)

    asyncio.run(throttle.close())
