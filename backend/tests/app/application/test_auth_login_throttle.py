from __future__ import annotations

import pytest
import redis

import app.application.auth.login_throttle as login_throttle_module
from app.application.auth.login_throttle import AuthLoginThrottle
from app.domain.auth.constants import ERROR_AUTH_RATE_LIMITED
from app.infrastructure.auth.login_throttle import RedisAuthLoginThrottle


def test_throttle_blocks_after_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    current = 100.0
    monkeypatch.setattr(login_throttle_module.time, "monotonic", lambda: current)

    throttle = AuthLoginThrottle(max_failures=2, window_seconds=60, block_seconds=120)
    throttle.record_failure(key="trader@example.com")
    throttle.assert_allowed(key="trader@example.com")

    throttle.record_failure(key="trader@example.com")
    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        throttle.assert_allowed(key="trader@example.com")


def test_throttle_caps_entry_growth_and_purges_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    current = 0.0
    monkeypatch.setattr(login_throttle_module.time, "monotonic", lambda: current)

    throttle = AuthLoginThrottle(max_failures=5, window_seconds=10, block_seconds=30, max_entries=2)
    throttle.record_failure(key="a@example.com")
    throttle.record_failure(key="b@example.com")
    throttle.record_failure(key="c@example.com")

    assert len(throttle._states) == 2
    assert "c@example.com" in throttle._states

    current = 20.0
    throttle.assert_allowed(key="d@example.com")
    assert len(throttle._states) == 0


class FakeRedisClient:
    def __init__(self, now_provider) -> None:
        self._now_provider = now_provider
        self._values: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}

    def get(self, key: str):
        self._purge_expired()
        return self._values.get(key)

    def incr(self, key: str) -> int:
        self._purge_expired()
        value = int(self._values.get(key, "0")) + 1
        self._values[key] = str(value)
        return value

    def ttl(self, key: str) -> int:
        self._purge_expired()
        if key not in self._values:
            return -2
        expire_at = self._expires_at.get(key)
        if expire_at is None:
            return -1
        return max(0, int(expire_at - self._now_provider()))

    def expire(self, key: str, seconds: int) -> bool:
        self._purge_expired()
        if key not in self._values:
            return False
        self._expires_at[key] = self._now_provider() + seconds
        return True

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._values[key] = value
        if ex is not None:
            self._expires_at[key] = self._now_provider() + ex
        return True

    def delete(self, *keys: str) -> int:
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


def test_redis_throttle_blocks_across_shared_client() -> None:
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

    throttle_a.record_failure(key="trader@example.com")
    throttle_b.assert_allowed(key="trader@example.com")

    throttle_b.record_failure(key="trader@example.com")
    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        throttle_a.assert_allowed(key="trader@example.com")

    current = 300.0
    throttle_b.assert_allowed(key="trader@example.com")


class BrokenRedisClient:
    def get(self, key: str):
        raise redis.ConnectionError("redis unavailable")

    def incr(self, key: str) -> int:
        raise redis.ConnectionError("redis unavailable")

    def ttl(self, key: str) -> int:
        raise redis.ConnectionError("redis unavailable")

    def expire(self, key: str, seconds: int) -> bool:
        raise redis.ConnectionError("redis unavailable")

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        raise redis.ConnectionError("redis unavailable")

    def delete(self, *keys: str) -> int:
        raise redis.ConnectionError("redis unavailable")


def test_redis_throttle_falls_back_to_in_memory_when_redis_fails() -> None:
    current = 100.0
    throttle = RedisAuthLoginThrottle(
        redis_url="redis://unused",
        max_failures=2,
        window_seconds=60,
        block_seconds=120,
        client=BrokenRedisClient(),
        time_provider=lambda: current,
    )

    throttle.record_failure(key="trader@example.com")
    throttle.assert_allowed(key="trader@example.com")

    throttle.record_failure(key="trader@example.com")
    with pytest.raises(ValueError, match=ERROR_AUTH_RATE_LIMITED):
        throttle.assert_allowed(key="trader@example.com")
