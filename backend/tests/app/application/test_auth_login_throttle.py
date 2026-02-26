from __future__ import annotations

import pytest

import app.application.auth.login_throttle as login_throttle_module
from app.application.auth.login_throttle import AuthLoginThrottle
from app.domain.auth.constants import ERROR_AUTH_RATE_LIMITED


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

    current = 20.0
    throttle.assert_allowed(key="d@example.com")
    assert len(throttle._states) == 0
