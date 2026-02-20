from __future__ import annotations

from datetime import date

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
) -> bool:
    days = (end_date - start_date).days
    if days <= 0:
        return False

    if timespan == "minute":
        estimated_points = (days * 24 * 60) // multiplier
    elif timespan == "day":
        estimated_points = days // multiplier
    elif timespan == "week":
        estimated_points = days // (7 * multiplier)
    else:
        estimated_points = days // (30 * multiplier)
    return estimated_points > MAX_ESTIMATED_POINTS

