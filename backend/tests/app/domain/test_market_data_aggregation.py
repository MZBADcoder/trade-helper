from __future__ import annotations

from datetime import datetime, timezone

from app.domain.market_data.aggregation import (
    aggregate_minute_bars,
    resolve_bucket_bounds,
    resolve_current_open_bucket,
)
from app.domain.market_data.schemas import MarketBar


def _minute_bar(*, start_at: datetime, close: float) -> MarketBar:
    return MarketBar(
        ticker="AAPL",
        timespan="minute",
        multiplier=1,
        start_at=start_at,
        open=close - 0.5,
        high=close + 0.5,
        low=close - 1.0,
        close=close,
        volume=100,
        vwap=close,
        trades=10,
        source="DB",
    )


def test_resolve_bucket_bounds_60m_supports_close_truncated_bucket() -> None:
    bucket_start, bucket_end = resolve_bucket_bounds(
        point=datetime(2026, 2, 10, 20, 45, tzinfo=timezone.utc),  # 15:45 ET
        multiplier=60,
    )

    assert bucket_start == datetime(2026, 2, 10, 20, 30, tzinfo=timezone.utc)  # 15:30 ET
    assert bucket_end == datetime(2026, 2, 10, 21, 0, tzinfo=timezone.utc)  # 16:00 ET


def test_resolve_bucket_bounds_handles_dst_offset() -> None:
    bucket_start, bucket_end = resolve_bucket_bounds(
        point=datetime(2026, 3, 9, 13, 31, tzinfo=timezone.utc),  # 09:31 ET (DST, UTC-4)
        multiplier=5,
    )

    assert bucket_start == datetime(2026, 3, 9, 13, 30, tzinfo=timezone.utc)
    assert bucket_end == datetime(2026, 3, 9, 13, 35, tzinfo=timezone.utc)


def test_aggregate_minute_bars_skips_unfinished_when_requested() -> None:
    now = datetime(2026, 2, 10, 15, 7, tzinfo=timezone.utc)  # 10:07 ET
    bars = [
        _minute_bar(start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc), close=100.0),
        _minute_bar(start_at=datetime(2026, 2, 10, 15, 1, tzinfo=timezone.utc), close=101.0),
        _minute_bar(start_at=datetime(2026, 2, 10, 15, 2, tzinfo=timezone.utc), close=102.0),
        _minute_bar(start_at=datetime(2026, 2, 10, 15, 3, tzinfo=timezone.utc), close=103.0),
        _minute_bar(start_at=datetime(2026, 2, 10, 15, 4, tzinfo=timezone.utc), close=104.0),
        _minute_bar(start_at=datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc), close=105.0),
        _minute_bar(start_at=datetime(2026, 2, 10, 15, 6, tzinfo=timezone.utc), close=106.0),
    ]

    result = aggregate_minute_bars(
        ticker="AAPL",
        multiplier=5,
        bars=bars,
        source="DB_AGG",
        now=now,
        include_unfinished=False,
    )

    assert len(result) == 1
    assert result[0].start_at == datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)
    assert result[0].is_final is True


def test_resolve_current_open_bucket_returns_none_after_market_close() -> None:
    bucket = resolve_current_open_bucket(
        now=datetime(2026, 2, 10, 22, 1, tzinfo=timezone.utc),  # 17:01 ET
        multiplier=15,
    )

    assert bucket is None
