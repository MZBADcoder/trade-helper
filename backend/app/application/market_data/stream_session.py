from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time

from app.application.market_data.stream_policy import SUPPORTED_STREAM_CHANNELS

_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")


@dataclass(slots=True, frozen=True)
class StreamClientAction:
    action: str
    symbols: set[str]
    channels: set[str]


@dataclass(slots=True, frozen=True)
class StreamActionError:
    code: str
    message: str


@dataclass(slots=True, frozen=True)
class StreamActionOutcome:
    changed: bool
    symbols: set[str]
    channels: set[str]
    error: StreamActionError | None = None


@dataclass(slots=True, frozen=True)
class StreamHeartbeatDecision:
    should_close: bool
    should_send_ping: bool
    sleep_seconds: float


class MarketStreamSession:
    def __init__(
        self,
        *,
        max_symbols: int,
        ping_interval_seconds: int,
        ping_timeout_seconds: int,
        ping_max_misses: int,
        allowed_channels: set[str] | None = None,
        default_channels: set[str] | None = None,
        now: float | None = None,
    ) -> None:
        base_now = now if now is not None else time.monotonic()
        self._max_symbols = max(1, max_symbols)
        self._ping_interval = max(1, ping_interval_seconds)
        self._ping_timeout = max(1, ping_timeout_seconds)
        self._ping_max_misses = max(1, ping_max_misses)
        self._heartbeat_check_interval = min(1.0, max(0.2, self._ping_timeout / 2))

        self._allowed_channels = _normalize_supported_channels(allowed_channels or SUPPORTED_STREAM_CHANNELS)
        configured_default_channels = default_channels if default_channels is not None else self._allowed_channels
        self._default_channels = _normalize_default_channels(
            configured_default_channels,
            allowed_channels=self._allowed_channels,
        )

        self._desired_symbols: set[str] = set()
        self._desired_channels: set[str] = set(self._default_channels)

        self._last_client_ping_at = base_now
        self._last_server_ping_at: float | None = None
        self._ping_deadline_at: float | None = None
        self._next_ping_at = base_now + self._ping_interval
        self._missed_ping_acks = 0

    @property
    def symbols(self) -> set[str]:
        return set(self._desired_symbols)

    @property
    def channels(self) -> set[str]:
        return set(self._desired_channels)

    def apply_action(
        self,
        action: StreamClientAction,
        *,
        allowed_symbols: set[str],
        now: float | None = None,
    ) -> StreamActionOutcome:
        if action.channels:
            try:
                requested_channels = _normalize_supported_channels(action.channels)
            except ValueError as exc:
                return StreamActionOutcome(
                    changed=False,
                    symbols=self.symbols,
                    channels=self.channels,
                    error=StreamActionError(
                        code=str(exc),
                        message="invalid stream channels",
                    ),
                )
            not_allowed_channels = requested_channels.difference(self._allowed_channels)
            if not_allowed_channels:
                blocked = ",".join(sorted(not_allowed_channels))
                return StreamActionOutcome(
                    changed=False,
                    symbols=self.symbols,
                    channels=self.channels,
                    error=StreamActionError(
                        code="STREAM_CHANNEL_NOT_ALLOWED",
                        message=f"channels not allowed in current mode: {blocked}",
                    ),
                )
            self._desired_channels = requested_channels

        if action.action in {"ping", "pong"}:
            self.touch_client_ping(now=now)
            return StreamActionOutcome(
                changed=False,
                symbols=self.symbols,
                channels=self.channels,
            )

        if action.action == "unsubscribe":
            self._desired_symbols = self._desired_symbols.difference(action.symbols)
            return StreamActionOutcome(
                changed=True,
                symbols=self.symbols,
                channels=self.channels,
            )

        if action.action != "subscribe":
            return StreamActionOutcome(
                changed=False,
                symbols=self.symbols,
                channels=self.channels,
                error=StreamActionError(
                    code="STREAM_INVALID_ACTION",
                    message=f"unsupported action: {action.action}",
                ),
            )

        if not action.symbols:
            return StreamActionOutcome(
                changed=False,
                symbols=self.symbols,
                channels=self.channels,
                error=StreamActionError(
                    code="STREAM_INVALID_ACTION",
                    message="subscribe requires symbols",
                ),
            )

        not_allowed = action.symbols.difference(allowed_symbols)
        if not_allowed:
            blocked = ",".join(sorted(not_allowed))
            return StreamActionOutcome(
                changed=False,
                symbols=self.symbols,
                channels=self.channels,
                error=StreamActionError(
                    code="STREAM_SYMBOL_NOT_ALLOWED",
                    message=f"symbols not in watchlist: {blocked}",
                ),
            )

        next_symbols = self._desired_symbols.union(action.symbols)
        if len(next_symbols) > self._max_symbols:
            return StreamActionOutcome(
                changed=False,
                symbols=self.symbols,
                channels=self.channels,
                error=StreamActionError(
                    code="STREAM_SUBSCRIPTION_LIMIT_EXCEEDED",
                    message=f"max {self._max_symbols} symbols per connection",
                ),
            )

        self._desired_symbols = next_symbols
        return StreamActionOutcome(
            changed=True,
            symbols=self.symbols,
            channels=self.channels,
        )

    def touch_client_ping(self, *, now: float | None = None) -> None:
        self._last_client_ping_at = now if now is not None else time.monotonic()

    def heartbeat_decision(self, *, now: float | None = None) -> StreamHeartbeatDecision:
        current = now if now is not None else time.monotonic()
        should_close = False

        if self._last_server_ping_at is not None and self._ping_deadline_at is not None:
            if self._last_client_ping_at >= self._last_server_ping_at:
                self._missed_ping_acks = 0
                self._last_server_ping_at = None
                self._ping_deadline_at = None
            elif current >= self._ping_deadline_at:
                self._missed_ping_acks += 1
                self._last_server_ping_at = None
                self._ping_deadline_at = None
                if self._missed_ping_acks >= self._ping_max_misses:
                    should_close = True

        should_send_ping = current >= self._next_ping_at
        sleep_seconds = min(
            self._heartbeat_check_interval,
            max(0.05, self._next_ping_at - current),
        )
        return StreamHeartbeatDecision(
            should_close=should_close,
            should_send_ping=should_send_ping,
            sleep_seconds=sleep_seconds,
        )

    def mark_ping_sent(self, *, sent_at: float | None = None) -> None:
        current = sent_at if sent_at is not None else time.monotonic()
        self._last_server_ping_at = current
        self._ping_deadline_at = current + self._ping_timeout
        self._next_ping_at = current + self._ping_interval


def parse_stream_action(raw: str) -> StreamClientAction | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    action = str(payload.get("action", "")).strip().lower()
    if not action:
        return None

    channels = _parse_channels(payload.get("channels"))
    if channels is None:
        return None

    return StreamClientAction(
        action=action,
        symbols=_parse_symbols(payload.get("symbols")),
        channels=channels,
    )


def _parse_symbols(raw: object) -> set[str]:
    if not isinstance(raw, list):
        return set()
    normalized: set[str] = set()
    for value in raw:
        symbol = str(value).strip().upper()
        if not symbol:
            continue
        if not _TICKER_PATTERN.fullmatch(symbol):
            continue
        normalized.add(symbol)
    return normalized


def _parse_channels(raw: object) -> set[str] | None:
    if raw is None:
        return set()
    if not isinstance(raw, list):
        return None

    normalized = {str(value).strip().lower() for value in raw if str(value).strip()}
    if not normalized:
        return set()
    if not normalized.issubset(SUPPORTED_STREAM_CHANNELS):
        return None
    return normalized


def _normalize_supported_channels(channels: set[str]) -> set[str]:
    normalized = {str(value).strip().lower() for value in channels if str(value).strip()}
    if not normalized:
        raise ValueError("STREAM_CHANNEL_NOT_ALLOWED")
    if not normalized.issubset(SUPPORTED_STREAM_CHANNELS):
        raise ValueError("STREAM_INVALID_ACTION")
    return normalized


def _normalize_default_channels(
    channels: set[str],
    *,
    allowed_channels: set[str],
) -> set[str]:
    normalized = _normalize_supported_channels(channels)
    if not normalized.issubset(allowed_channels):
        raise ValueError("STREAM_CHANNEL_NOT_ALLOWED")
    return normalized
