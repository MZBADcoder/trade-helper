from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
import threading
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
from exchange_calendars.errors import DateOutOfBounds
import pandas as pd

from app.infrastructure.clients.massive import MassiveClient

MARKET_TIMEZONE = ZoneInfo("America/New_York")
_HOLIDAY_CACHE_TTL = timedelta(minutes=15)

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class _HolidayOverride:
    trade_date: date
    closed: bool
    open_time: time | None
    close_time: time | None


class TradingCalendar:
    def __init__(
        self,
        *,
        massive_client: MassiveClient | None,
        exchange: str = "XNYS",
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self._massive_client = massive_client
        self._exchange_calendar = xcals.get_calendar(exchange)
        self._today_provider = today_provider or date.today
        self._holiday_overrides: dict[date, _HolidayOverride] = {}
        self._holiday_cache_expire_at: datetime | None = None
        self._holiday_cache_lock = threading.Lock()

    def is_trading_day(self, *, target_date: date) -> bool:
        return self.session_minutes(target_date=target_date) > 0

    def session_minutes(self, *, target_date: date) -> int:
        base_minutes = self._base_session_minutes(target_date=target_date)
        if target_date < self._today_provider():
            return base_minutes

        override = self._holiday_override(target_date=target_date)
        if override is None:
            return base_minutes
        if override.closed:
            return 0
        if override.open_time is None or override.close_time is None:
            return base_minutes

        opened_at = datetime.combine(target_date, override.open_time, tzinfo=MARKET_TIMEZONE)
        closed_at = datetime.combine(target_date, override.close_time, tzinfo=MARKET_TIMEZONE)
        return max(0, int((closed_at - opened_at).total_seconds() // 60))

    def count_trading_days(
        self,
        *,
        start_date: date,
        end_date: date,
        max_count: int | None = None,
    ) -> int:
        if end_date < start_date:
            return 0

        count = 0
        cursor = start_date
        while cursor <= end_date:
            if self.is_trading_day(target_date=cursor):
                count += 1
                if max_count is not None and count > max_count:
                    return count
            cursor += timedelta(days=1)
        return count

    def count_session_minutes(
        self,
        *,
        start_date: date,
        end_date: date,
        max_minutes: int | None = None,
    ) -> int:
        if end_date < start_date:
            return 0

        total_minutes = 0
        cursor = start_date
        while cursor <= end_date:
            total_minutes += self.session_minutes(target_date=cursor)
            if max_minutes is not None and total_minutes > max_minutes:
                return total_minutes
            cursor += timedelta(days=1)
        return total_minutes

    def align_on_or_before(self, *, target_date: date) -> date:
        cursor = target_date
        while True:
            if self.is_trading_day(target_date=cursor):
                return cursor
            cursor -= timedelta(days=1)

    def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
        cursor = self.align_on_or_before(target_date=target_date)
        if trading_days == 0:
            return cursor

        step = 1 if trading_days > 0 else -1
        remaining = abs(trading_days)
        while remaining > 0:
            cursor += timedelta(days=step)
            if self.is_trading_day(target_date=cursor):
                remaining -= 1
        return cursor

    def list_recent_trading_days(self, *, end_date: date, count: int) -> list[date]:
        if count < 1:
            raise ValueError("count must be >= 1")

        aligned_end = self.align_on_or_before(target_date=end_date)
        result = [aligned_end]
        while len(result) < count:
            previous = self.shift_trading_day(target_date=result[-1], trading_days=-1)
            result.append(previous)
        result.reverse()
        return result

    def _base_session_minutes(self, *, target_date: date) -> int:
        session = pd.Timestamp(target_date.isoformat())
        try:
            if not self._exchange_calendar.is_session(session):
                return 0
            opened_at = self._exchange_calendar.session_open(session)
            closed_at = self._exchange_calendar.session_close(session)
            return max(0, int((closed_at - opened_at).total_seconds() // 60))
        except DateOutOfBounds:
            if target_date.weekday() >= 5:
                return 0
            return 390

    def _holiday_override(self, *, target_date: date) -> _HolidayOverride | None:
        if self._massive_client is None:
            return None

        now = datetime.now(tz=MARKET_TIMEZONE)
        if self._holiday_cache_expire_at is None or now >= self._holiday_cache_expire_at:
            with self._holiday_cache_lock:
                refreshed_now = datetime.now(tz=MARKET_TIMEZONE)
                if self._holiday_cache_expire_at is None or refreshed_now >= self._holiday_cache_expire_at:
                    self._holiday_overrides = self._fetch_holiday_overrides()
                    self._holiday_cache_expire_at = refreshed_now + _HOLIDAY_CACHE_TTL
        return self._holiday_overrides.get(target_date)

    def _fetch_holiday_overrides(self) -> dict[date, _HolidayOverride]:
        try:
            raw_holidays = self._massive_client.list_market_holidays()
        except Exception:
            logger.exception("Failed to fetch market holiday overrides from Massive")
            return {}

        overrides: dict[date, _HolidayOverride] = {}
        for raw in raw_holidays:
            parsed = _parse_holiday_override(raw)
            if parsed is not None:
                overrides[parsed.trade_date] = parsed
        return overrides


def _parse_holiday_override(raw: object) -> _HolidayOverride | None:
    raw_date = _extract_value(raw, "date")
    trade_date = _parse_date(raw_date)
    if trade_date is None:
        return None

    status = (_extract_value(raw, "status") or "").strip().lower()
    open_time = _parse_time(_extract_value(raw, "open"))
    close_time = _parse_time(_extract_value(raw, "close"))

    closed = "closed" in status and "early" not in status
    if open_time is None or close_time is None:
        return _HolidayOverride(
            trade_date=trade_date,
            closed=closed,
            open_time=open_time,
            close_time=close_time,
        )

    if close_time <= open_time:
        closed = True
    return _HolidayOverride(
        trade_date=trade_date,
        closed=closed,
        open_time=open_time,
        close_time=close_time,
    )


def _extract_value(raw: object, key: str) -> str:
    if isinstance(raw, dict):
        value = raw.get(key)
    else:
        value = getattr(raw, key, None)
    if value is None:
        return ""
    return str(value).strip()


def _parse_date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_time(raw: str) -> time | None:
    if not raw:
        return None

    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None

    if parsed is not None:
        if parsed.tzinfo is not None:
            return parsed.astimezone(MARKET_TIMEZONE).time().replace(tzinfo=None)
        return parsed.time()

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None
