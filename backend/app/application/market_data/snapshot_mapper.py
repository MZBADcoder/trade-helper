from __future__ import annotations

from datetime import datetime, timezone

from app.domain.market_data.schemas import MarketSnapshot


def to_market_snapshot(raw: object) -> MarketSnapshot | None:
    ticker = _extract_str(raw, "ticker", "symbol")
    if not ticker:
        return None

    updated_at = _extract_datetime(raw, "updated_at", "updated", "timestamp", "t")
    if updated_at is None:
        updated_at = datetime.now(tz=timezone.utc)

    return MarketSnapshot(
        ticker=ticker.upper(),
        last=_extract_float(raw, "last", "price", "last_trade.price"),
        change=_extract_float(raw, "change", "todays_change"),
        change_pct=_extract_float(raw, "change_pct", "todays_change_perc", "todays_change_percent"),
        open=_extract_float(raw, "open", "day.open"),
        high=_extract_float(raw, "high", "day.high"),
        low=_extract_float(raw, "low", "day.low"),
        volume=int(_extract_float(raw, "volume", "day.volume")),
        updated_at=updated_at,
        market_status=_extract_str(raw, "market_status") or "unknown",
        source=(_extract_str(raw, "source") or "REST").upper(),
    )


def _extract_value(raw: object, key: str) -> object | None:
    parts = key.split(".")
    current: object | None = raw
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if hasattr(current, part):
            current = getattr(current, part)
            continue
        return None
    return current


def _extract_str(raw: object, *keys: str) -> str:
    for key in keys:
        value = _extract_value(raw, key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _extract_float(raw: object, *keys: str) -> float:
    for key in keys:
        value = _extract_value(raw, key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _extract_datetime(raw: object, *keys: str) -> datetime | None:
    value: object | None = None
    for key in keys:
        value = _extract_value(raw, key)
        if value is not None:
            break
    if value is None:
        return None
    return _to_utc_datetime(value)


def _to_utc_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        numeric = float(value)
        abs_value = abs(numeric)
        if abs_value >= 10_000_000_000_000:
            numeric = numeric / 1_000_000_000.0
        elif abs_value >= 10_000_000_000:
            numeric = numeric / 1_000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None

