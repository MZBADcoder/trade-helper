from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.application.demo_market.service import (
    DEMO_TICKER,
    DemoAggregateStreamEvent,
    DemoMarketDataApplicationService,
    DemoQuoteStreamEvent,
    DemoTradeStreamEvent,
)
from app.application.market_data.trading_calendar import TradingCalendar


def _build_demo_service(
    *,
    now: datetime,
    today: date,
) -> DemoMarketDataApplicationService:
    calendar = TradingCalendar(
        massive_client=None,
        today_provider=lambda: today,
    )
    return DemoMarketDataApplicationService(
        trading_calendar=calendar,
        now_provider=lambda: now,
    )


def test_demo_replay_window_is_stable_and_fixed_length() -> None:
    service = _build_demo_service(
        now=datetime(2026, 2, 27, 14, 0, 0, tzinfo=timezone.utc),
        today=date(2026, 2, 27),
    )

    first = service.replay_window()
    second = service.replay_window()

    assert first.trade_date == date(2026, 2, 26)
    assert first.size == 30
    assert [item.start_at for item in first.bars] == [item.start_at for item in second.bars]
    assert [item.close for item in first.bars] == [item.close for item in second.bars]
    assert all(item.ticker == DEMO_TICKER for item in first.bars)


def test_demo_bars_reject_non_amd_ticker() -> None:
    service = _build_demo_service(
        now=datetime(2026, 2, 27, 14, 0, 0, tzinfo=timezone.utc),
        today=date(2026, 2, 27),
    )

    with pytest.raises(ValueError, match="AMD"):
        service.list_bars_with_meta(
            ticker="AAPL",
            timespan="minute",
            multiplier=1,
        )


def test_demo_stream_events_include_supported_market_messages() -> None:
    service = _build_demo_service(
        now=datetime(2026, 2, 27, 14, 0, 0, tzinfo=timezone.utc),
        today=date(2026, 2, 27),
    )

    events = service.stream_events(step=7, channels={"quote", "trade", "aggregate"})

    assert [type(item) for item in events] == [
        DemoQuoteStreamEvent,
        DemoTradeStreamEvent,
        DemoAggregateStreamEvent,
    ]
    for item in events:
        assert item.symbol == DEMO_TICKER
        assert isinstance(item.replay_index, int)
