from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from contextlib import asynccontextmanager
import threading
from typing import Callable
import time

import redis.asyncio as redis

from app.domain.auth.constants import ERROR_AUTH_RATE_LIMITED


@dataclass(slots=True)
class _ThrottleState:
    failures: int
    window_started_at: float
    blocked_until: float


class _FallbackLoginThrottle:
    def __init__(
        self,
        *,
        max_failures: int,
        window_seconds: int,
        block_seconds: int,
        max_entries: int = 10000,
        time_provider: Callable[[], float],
    ) -> None:
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._block_seconds = block_seconds
        self._max_entries = max_entries
        self._time_provider = time_provider
        self._states: dict[str, _ThrottleState] = {}
        self._lock = threading.Lock()

    async def assert_allowed(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return
        now = self._time_provider()
        with self._lock:
            self._purge_expired(now=now)
            state = self._states.get(normalized)
            if state is not None and state.blocked_until > now:
                raise ValueError(ERROR_AUTH_RATE_LIMITED)

    async def record_failure(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return
        now = self._time_provider()
        with self._lock:
            self._purge_expired(now=now)
            state = self._states.get(normalized)
            if state is None and len(self._states) >= self._max_entries:
                self._evict_oldest_entry()
            if state is None or now - state.window_started_at > self._window_seconds:
                self._states[normalized] = _ThrottleState(failures=1, window_started_at=now, blocked_until=0)
                return

            failures = state.failures + 1
            blocked_until = state.blocked_until
            if failures >= self._max_failures:
                blocked_until = max(blocked_until, now + self._block_seconds)
            self._states[normalized] = _ThrottleState(
                failures=failures,
                window_started_at=state.window_started_at,
                blocked_until=blocked_until,
            )

    async def record_success(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if normalized:
            with self._lock:
                self._states.pop(normalized, None)

    def _purge_expired(self, *, now: float) -> None:
        expired_keys = [
            key
            for key, state in self._states.items()
            if state.blocked_until <= now and now - state.window_started_at > self._window_seconds
        ]
        for key in expired_keys:
            self._states.pop(key, None)

    def _evict_oldest_entry(self) -> None:
        if not self._states:
            return
        oldest_key = min(
            self._states,
            key=lambda item_key: (
                self._states[item_key].window_started_at,
                self._states[item_key].blocked_until,
            ),
        )
        self._states.pop(oldest_key, None)


class RedisAuthLoginThrottle:
    def __init__(
        self,
        *,
        redis_url: str,
        max_failures: int = 8,
        window_seconds: int = 5 * 60,
        block_seconds: int = 10 * 60,
        key_prefix: str = "auth:login-throttle",
        client: redis.Redis | None = None,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._max_failures = max(1, int(max_failures))
        self._window_seconds = max(1, int(window_seconds))
        self._block_seconds = max(1, int(block_seconds))
        self._key_prefix = key_prefix.strip() or "auth:login-throttle"
        self._client = client
        self._time_provider = time_provider or time.time
        self._fallback = _FallbackLoginThrottle(
            max_failures=self._max_failures,
            window_seconds=self._window_seconds,
            block_seconds=self._block_seconds,
            time_provider=self._time_provider,
        )

    async def assert_allowed(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return

        try:
            async with self._client_scope() as client:
                blocked_until = await client.get(self._blocked_key(normalized))
        except redis.RedisError:
            await self._fallback.assert_allowed(key=normalized)
            return
        if blocked_until is None:
            return
        try:
            blocked_at = float(blocked_until)
        except (TypeError, ValueError):
            return
        if blocked_at > self._time_provider():
            raise ValueError(ERROR_AUTH_RATE_LIMITED)

    async def record_failure(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return

        try:
            async with self._client_scope() as client:
                failures_key = self._failures_key(normalized)
                blocked_key = self._blocked_key(normalized)
                failures = int(await client.incr(failures_key))
                if int(await client.ttl(failures_key)) < 0:
                    await client.expire(failures_key, self._window_seconds)

                if failures >= self._max_failures:
                    blocked_until = self._time_provider() + self._block_seconds
                    await client.set(blocked_key, str(blocked_until), ex=self._block_seconds)
        except redis.RedisError:
            await self._fallback.record_failure(key=normalized)

    async def record_success(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return
        try:
            async with self._client_scope() as client:
                await client.delete(
                    self._failures_key(normalized),
                    self._blocked_key(normalized),
                )
        except redis.RedisError:
            await self._fallback.record_success(key=normalized)

    async def close(self) -> None:
        if self._client is not None:
            return

    @asynccontextmanager
    async def _client_scope(self) -> AsyncIterator[redis.Redis]:
        if self._client is not None:
            yield self._client
            return

        client = redis.Redis.from_url(self._redis_url, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    def _failures_key(self, normalized: str) -> str:
        return f"{self._key_prefix}:failures:{normalized}"

    def _blocked_key(self, normalized: str) -> str:
        return f"{self._key_prefix}:blocked:{normalized}"
