from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.market_data.trading_calendar import TradingCalendar

SUPPORTED_TIMESPANS = {"minute", "day", "week", "month"}
MIN_MULTIPLIER = 1
MAX_MULTIPLIER = 60
MAX_ESTIMATED_POINTS = 5000


def normalize_timespan(raw: str) -> str:
    return raw.strip().lower()


def is_supported_timespan(timespan: str) -> bool:
    return timespan in SUPPORTED_TIMESPANS


def is_valid_multiplier(multiplier: int) -> bool:
    return MIN_MULTIPLIER <= multiplier <= MAX_MULTIPLIER


def is_range_too_large(
    *,
    timespan: str,
    multiplier: int,
    start_date: date,
    end_date: date,
    trading_calendar: TradingCalendar | None = None,
) -> bool:
    days = (end_date - start_date).days
    if days <= 0:
        return False

    if timespan == "minute":
        if trading_calendar is None:
            estimated_points = (days * 24 * 60) // multiplier
        else:
            max_minutes = (MAX_ESTIMATED_POINTS + 1) * multiplier
            total_minutes = trading_calendar.count_session_minutes(
                start_date=start_date,
                end_date=end_date,
                max_minutes=max_minutes,
            )
            estimated_points = total_minutes // multiplier
    elif timespan == "day":
        if trading_calendar is None:
            estimated_points = days // multiplier
        else:
            max_days = (MAX_ESTIMATED_POINTS + 1) * multiplier
            trading_days = trading_calendar.count_trading_days(
                start_date=start_date,
                end_date=end_date,
                max_count=max_days,
            )
            estimated_points = trading_days // multiplier
    elif timespan == "week":
        if trading_calendar is None:
            estimated_points = days // (7 * multiplier)
        else:
            trading_days = trading_calendar.count_trading_days(
                start_date=start_date,
                end_date=end_date,
            )
            estimated_points = trading_days // (5 * multiplier)
    else:
        if trading_calendar is None:
            estimated_points = days // (30 * multiplier)
        else:
            trading_days = trading_calendar.count_trading_days(
                start_date=start_date,
                end_date=end_date,
            )
            estimated_points = trading_days // (21 * multiplier)
    return estimated_points > MAX_ESTIMATED_POINTS
