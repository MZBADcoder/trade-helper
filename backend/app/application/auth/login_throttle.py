from __future__ import annotations

from dataclasses import dataclass
import threading
import time

from app.domain.auth.constants import ERROR_AUTH_RATE_LIMITED


@dataclass(slots=True)
class _ThrottleState:
    failures: int
    window_started_at: float
    blocked_until: float


class AuthLoginThrottle:
    def __init__(
        self,
        *,
        max_failures: int = 8,
        window_seconds: int = 5 * 60,
        block_seconds: int = 10 * 60,
        max_entries: int = 10000,
    ) -> None:
        self._max_failures = max(1, int(max_failures))
        self._window_seconds = max(1, int(window_seconds))
        self._block_seconds = max(1, int(block_seconds))
        self._max_entries = max(1, int(max_entries))
        self._states: dict[str, _ThrottleState] = {}
        self._lock = threading.Lock()

    def assert_allowed(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return

        now = time.monotonic()
        with self._lock:
            self._purge_expired(now=now)
            state = self._states.get(normalized)
            if state is None:
                return
            if state.blocked_until > now:
                raise ValueError(ERROR_AUTH_RATE_LIMITED)

    def record_failure(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return

        now = time.monotonic()
        with self._lock:
            self._purge_expired(now=now)
            state = self._states.get(normalized)
            if state is None and len(self._states) >= self._max_entries:
                self._evict_oldest_entry()
            if state is None or now - state.window_started_at > self._window_seconds:
                self._states[normalized] = _ThrottleState(
                    failures=1,
                    window_started_at=now,
                    blocked_until=0,
                )
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

    def record_success(self, *, key: str) -> None:
        normalized = key.strip().lower()
        if not normalized:
            return
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
