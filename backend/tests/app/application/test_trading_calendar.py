from __future__ import annotations

from datetime import date
from concurrent.futures import ThreadPoolExecutor

from app.application.market_data.trading_calendar import TradingCalendar


class HolidayStubMassiveClient:
    def __init__(self, holidays: list[dict]) -> None:
        self._holidays = holidays
        self.calls = 0

    def list_market_holidays(self) -> list[dict]:
        self.calls += 1
        return list(self._holidays)


def test_list_recent_trading_days_skips_weekend() -> None:
    calendar = TradingCalendar(
        massive_client=None,
        today_provider=lambda: date(2026, 2, 24),
    )

    days = calendar.list_recent_trading_days(
        end_date=date(2026, 2, 24),
        count=3,
    )

    assert days == [date(2026, 2, 20), date(2026, 2, 23), date(2026, 2, 24)]


def test_session_minutes_uses_exchange_half_day_schedule() -> None:
    calendar = TradingCalendar(
        massive_client=None,
        today_provider=lambda: date(2026, 11, 27),
    )

    assert calendar.session_minutes(target_date=date(2026, 11, 27)) == 210


def test_count_session_minutes_excludes_non_trading_days() -> None:
    calendar = TradingCalendar(
        massive_client=None,
        today_provider=lambda: date(2026, 2, 24),
    )

    total = calendar.count_session_minutes(
        start_date=date(2026, 2, 20),
        end_date=date(2026, 2, 24),
    )

    assert total == 390 * 3


def test_massive_holiday_override_marks_future_day_closed() -> None:
    calendar = TradingCalendar(
        massive_client=HolidayStubMassiveClient(
            holidays=[
                {
                    "date": "2026-02-25",
                    "status": "closed",
                }
            ]
        ),
        today_provider=lambda: date(2026, 2, 24),
    )

    assert calendar.is_trading_day(target_date=date(2026, 2, 25)) is False
    assert calendar.session_minutes(target_date=date(2026, 2, 25)) == 0


def test_massive_holiday_override_can_apply_early_close_minutes() -> None:
    calendar = TradingCalendar(
        massive_client=HolidayStubMassiveClient(
            holidays=[
                {
                    "date": "2026-02-26",
                    "status": "early-close",
                    "open": "09:30",
                    "close": "13:00",
                }
            ]
        ),
        today_provider=lambda: date(2026, 2, 24),
    )

    assert calendar.session_minutes(target_date=date(2026, 2, 26)) == 210


def test_holiday_override_cache_refresh_is_thread_safe() -> None:
    client = HolidayStubMassiveClient(
        holidays=[
            {
                "date": "2026-02-26",
                "status": "early-close",
                "open": "09:30",
                "close": "13:00",
            }
        ]
    )
    calendar = TradingCalendar(
        massive_client=client,
        today_provider=lambda: date(2026, 2, 24),
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda _: calendar.session_minutes(target_date=date(2026, 2, 26)),
                range(16),
            )
        )

    assert client.calls == 1
