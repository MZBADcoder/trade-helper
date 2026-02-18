from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.domain.market_data.schemas import MarketBar

MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_OPEN_TIME = time(9, 30)
MARKET_CLOSE_TIME = time(16, 0)


def market_trade_date(*, point: datetime) -> date:
    return _as_market_time(point).date()


def resolve_bucket_bounds(*, point: datetime, multiplier: int) -> tuple[datetime, datetime]:
    if multiplier < 1:
        raise ValueError("Multiplier must be >= 1")

    local_point = _as_market_time(point)
    session_open, session_close = _session_bounds(local_point.date())

    last_usable_point = session_close - timedelta(microseconds=1)
    clamped = min(max(local_point, session_open), last_usable_point)
    elapsed_minutes = int((clamped - session_open).total_seconds() // 60)
    bucket_index = elapsed_minutes // multiplier

    bucket_start = session_open + timedelta(minutes=bucket_index * multiplier)
    bucket_end = min(bucket_start + timedelta(minutes=multiplier), session_close)
    return bucket_start.astimezone(timezone.utc), bucket_end.astimezone(timezone.utc)


def resolve_current_open_bucket(*, now: datetime, multiplier: int) -> tuple[datetime, datetime] | None:
    local_now = _as_market_time(now)
    session_open, session_close = _session_bounds(local_now.date())
    if local_now < session_open or local_now >= session_close:
        return None
    return resolve_bucket_bounds(point=now, multiplier=multiplier)


def is_bucket_final(*, bucket_end: datetime, now: datetime) -> bool:
    return _to_utc(bucket_end) <= _to_utc(now)


def aggregate_bucket(
    *,
    ticker: str,
    multiplier: int,
    bars: list[MarketBar],
    bucket_start: datetime,
    bucket_end: datetime,
    source: str,
    is_final: bool,
) -> MarketBar | None:
    if not bars:
        return None

    sorted_bars = sorted(bars, key=lambda bar: bar.start_at)
    first = sorted_bars[0]
    last = sorted_bars[-1]

    high = max(bar.high for bar in sorted_bars)
    low = min(bar.low for bar in sorted_bars)
    total_volume = sum(bar.volume for bar in sorted_bars)
    trades = sum(bar.trades or 0 for bar in sorted_bars)

    weighted_vwap_base = 0.0
    for bar in sorted_bars:
        price_for_weight = bar.vwap if bar.vwap is not None else bar.close
        weighted_vwap_base += price_for_weight * bar.volume
    vwap = (weighted_vwap_base / total_volume) if total_volume > 0 else None

    return MarketBar(
        ticker=ticker,
        timespan="minute",
        multiplier=multiplier,
        start_at=_to_utc(bucket_start),
        end_at=_to_utc(bucket_end),
        open=first.open,
        high=high,
        low=low,
        close=last.close,
        volume=total_volume,
        vwap=vwap,
        trades=trades,
        source=source,
        is_final=is_final,
    )


def aggregate_minute_bars(
    *,
    ticker: str,
    multiplier: int,
    bars: list[MarketBar],
    source: str,
    now: datetime,
    include_unfinished: bool,
) -> list[MarketBar]:
    grouped: dict[tuple[datetime, datetime], list[MarketBar]] = defaultdict(list)
    for bar in bars:
        bucket_start, bucket_end = resolve_bucket_bounds(point=bar.start_at, multiplier=multiplier)
        grouped[(bucket_start, bucket_end)].append(bar)

    aggregated: list[MarketBar] = []
    for (bucket_start, bucket_end), grouped_bars in grouped.items():
        final = is_bucket_final(bucket_end=bucket_end, now=now)
        if not include_unfinished and not final:
            continue
        item = aggregate_bucket(
            ticker=ticker,
            multiplier=multiplier,
            bars=grouped_bars,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            source=source,
            is_final=final,
        )
        if item is not None:
            aggregated.append(item)

    aggregated.sort(key=lambda bar: bar.start_at)
    return aggregated


def _session_bounds(trade_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(trade_date, MARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
    end = datetime.combine(trade_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE)
    return start, end


def _as_market_time(point: datetime) -> datetime:
    return _to_utc(point).astimezone(MARKET_TIMEZONE)


def _to_utc(point: datetime) -> datetime:
    if point.tzinfo is None:
        return point.replace(tzinfo=timezone.utc)
    return point.astimezone(timezone.utc)
