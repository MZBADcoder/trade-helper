from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def map_massive_event_to_market_message(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = str(event.get("ev", "")).upper()
    symbol = str(event.get("sym", "")).strip().upper()
    if not symbol:
        return None

    if event_type == "Q":
        return {
            "type": "market.quote",
            "ts": utc_now_iso(),
            "source": "WS",
            "data": {
                "symbol": symbol,
                "event_ts": to_iso_datetime(event.get("t")),
                "bid": to_float(event.get("bp")),
                "ask": to_float(event.get("ap")),
                "bid_size": to_float(event.get("bs")),
                "ask_size": to_float(event.get("as")),
            },
        }

    if event_type == "T":
        price = to_float(event.get("p"))
        return {
            "type": "market.trade",
            "ts": utc_now_iso(),
            "source": "WS",
            "data": {
                "symbol": symbol,
                "event_ts": to_iso_datetime(event.get("t")),
                "price": price,
                "last": price,
                "size": to_float(event.get("s")),
            },
        }

    if event_type in {"A", "AM"}:
        close = to_float(event.get("c"))
        return {
            "type": "market.aggregate",
            "ts": utc_now_iso(),
            "source": "WS",
            "data": {
                "symbol": symbol,
                "event_ts": to_iso_datetime(event.get("e")),
                "start_at": to_iso_datetime(event.get("s")),
                "end_at": to_iso_datetime(event.get("e")),
                "timespan": "minute" if event_type == "AM" else "second",
                "multiplier": 1,
                "open": to_float(event.get("o")),
                "high": to_float(event.get("h")),
                "low": to_float(event.get("l")),
                "close": close,
                "last": close,
                "volume": to_float(event.get("v")),
                "vwap": to_float(event.get("vw")),
            },
        }

    return None


def build_system_status(*, latency: str, connection_state: str, message: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "latency": latency,
        "connection_state": connection_state,
    }
    if message:
        data["message"] = message
    return {
        "type": "system.status",
        "ts": utc_now_iso(),
        "source": "WS",
        "data": data,
    }


def build_system_error(*, code: str, message: str) -> dict[str, Any]:
    return {
        "type": "system.error",
        "ts": utc_now_iso(),
        "source": "WS",
        "data": {
            "code": code,
            "message": message,
        },
    }


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def to_iso_datetime(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        normalized = stripped.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    if isinstance(value, (int, float)):
        numeric = float(value)
        abs_value = abs(numeric)
        if abs_value >= 1_000_000_000_000_000_000:
            numeric = numeric / 1_000_000_000.0
        elif abs_value >= 1_000_000_000_000_000:
            numeric = numeric / 1_000_000.0
        elif abs_value >= 1_000_000_000_000:
            numeric = numeric / 1_000.0
        parsed = datetime.fromtimestamp(numeric, tz=timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z")
    return None


def to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
