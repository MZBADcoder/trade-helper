from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from app.domain.market_data.schemas import MarketBar


def map_polygon_aggregates_to_market_bars(
    *,
    ticker: str,
    timespan: str,
    multiplier: int,
    aggregates: Iterable[object],
) -> list[MarketBar]:
    bars: list[MarketBar] = []
    for aggregate in aggregates:
        start_at = _to_utc_datetime(_extract_agg_value(aggregate, "timestamp", "t", "start_timestamp"))
        if start_at is None:
            continue

        bars.append(
            MarketBar(
                ticker=ticker,
                timespan=timespan,
                multiplier=multiplier,
                start_at=start_at,
                open=_extract_agg_float(aggregate, "open", "o"),
                high=_extract_agg_float(aggregate, "high", "h"),
                low=_extract_agg_float(aggregate, "low", "l"),
                close=_extract_agg_float(aggregate, "close", "c"),
                volume=_extract_agg_float(aggregate, "volume", "v"),
                vwap=_extract_optional_float(aggregate, "vwap", "vw"),
                trades=_extract_optional_int(aggregate, "transactions", "trades", "n"),
            )
        )

    return bars


def _extract_agg_value(aggregate: object, *keys: str) -> object | None:
    if isinstance(aggregate, dict):
        for key in keys:
            value = aggregate.get(key)
            if value is not None:
                return value
        return None

    for key in keys:
        if hasattr(aggregate, key):
            value = getattr(aggregate, key)
            if value is not None:
                return value
    return None


def _extract_agg_float(aggregate: object, *keys: str) -> float:
    value = _extract_agg_value(aggregate, *keys)
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_optional_float(aggregate: object, *keys: str) -> float | None:
    value = _extract_agg_value(aggregate, *keys)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_optional_int(aggregate: object, *keys: str) -> int | None:
    value = _extract_agg_value(aggregate, *keys)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_utc_datetime(value: object | None) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        numeric = float(value)
        abs_value = abs(numeric)
        # Polygon timestamps are usually in ms; keep compatibility with second/ns inputs.
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
