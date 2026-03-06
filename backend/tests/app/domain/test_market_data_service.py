from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.application.market_data.errors import MarketDataRangeTooLargeError, MarketDataUpstreamUnavailableError
from app.application.market_data import service as market_data_service_module
from app.application.market_data.service import MarketDataApplicationService
from app.domain.market_data.schemas import MarketBar

_MARKET_TZ = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def _stable_market_data_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(market_data_service_module.settings, "market_data_minute_finalize_delay_minutes", 5)
    monkeypatch.setattr(market_data_service_module.settings, "market_data_day_finalize_trade_days", 1)


def _bar(
    *,
    ticker: str,
    start_at: datetime,
    open: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.5,
    volume: float = 1000.0,
    timespan: str = "minute",
    multiplier: int = 1,
    source: str = "DB",
    end_at: datetime | None = None,
    is_final: bool | None = True,
) -> MarketBar:
    return MarketBar(
        ticker=ticker,
        timespan=timespan,
        multiplier=multiplier,
        start_at=start_at,
        end_at=end_at,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        vwap=None,
        trades=10,
        source=source,
        is_final=is_final,
    )


def _to_epoch_millis(value: datetime) -> int:
    return int(value.timestamp() * 1000)


class FakeMarketDataRepository:
    def __init__(self) -> None:
        self.day_bars: list[MarketBar] = []
        self.minute_bars: list[MarketBar] = []
        self.minute_agg_bars: list[MarketBar] = []
        self.minute_trade_dates: list[date] = []
        self.minute_agg_trade_dates: list[date] = []

        self.day_coverage: tuple[datetime, datetime] | None = None
        self.minute_coverage: tuple[datetime, datetime] | None = None
        self.minute_agg_coverage: tuple[datetime, datetime] | None = None

        self.upserted_day: list[MarketBar] = []
        self.upserted_minute: list[MarketBar] = []
        self.upserted_minute_agg: list[MarketBar] = []

        self.minute_delete_return = 0
        self.minute_agg_delete_return = 0
        self.deleted_minute_cutoff: date | None = None
        self.deleted_minute_agg_cutoff: date | None = None

    async def list_day_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]:
        return _filter_by_range(self.day_bars, ticker=ticker, start_at=start_at, end_at=end_at, limit=limit)

    async def list_minute_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
        session: str | None = None,
    ) -> list[MarketBar]:
        return _filter_by_range(
            self.minute_bars,
            ticker=ticker,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            session=session,
        )

    async def list_minute_agg_bars(
        self,
        *,
        ticker: str,
        multiplier: int,
        start_at: datetime,
        end_at: datetime,
        final_only: bool = True,
        limit: int | None = None,
    ) -> list[MarketBar]:
        items = [
            bar
            for bar in self.minute_agg_bars
            if bar.ticker == ticker
            and bar.multiplier == multiplier
            and start_at <= bar.start_at <= end_at
            and (not final_only or bar.is_final is not False)
        ]
        items.sort(key=lambda bar: bar.start_at)
        if limit and limit > 0:
            return items[:limit]
        return items

    async def list_minute_bars_for_bucket(
        self,
        *,
        ticker: str,
        bucket_start_at: datetime,
        bucket_end_at: datetime,
    ) -> list[MarketBar]:
        items = [
            bar
            for bar in self.minute_bars
            if bar.ticker == ticker and bucket_start_at <= bar.start_at < bucket_end_at
        ]
        items.sort(key=lambda bar: bar.start_at)
        return items

    async def get_day_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        _ = ticker
        return self.day_coverage

    async def get_minute_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        _ = ticker
        return self.minute_coverage

    async def get_minute_agg_range_coverage(
        self,
        *,
        ticker: str,
        multiplier: int,
    ) -> tuple[datetime, datetime] | None:
        _ = (ticker, multiplier)
        return self.minute_agg_coverage

    async def upsert_day_bars(self, bars: list[MarketBar]) -> None:
        self.upserted_day.extend(bars)
        merged = {bar.start_at: bar for bar in self.day_bars}
        for bar in bars:
            merged[bar.start_at] = bar
        self.day_bars = sorted(merged.values(), key=lambda bar: bar.start_at)

    async def upsert_minute_bars(self, bars: list[MarketBar]) -> None:
        self.upserted_minute.extend(bars)
        merged = {bar.start_at: bar for bar in self.minute_bars}
        for bar in bars:
            merged[bar.start_at] = bar
        self.minute_bars = sorted(merged.values(), key=lambda bar: bar.start_at)

    async def upsert_minute_agg_bars(self, bars: list[MarketBar]) -> None:
        self.upserted_minute_agg.extend(bars)
        merged = {(bar.multiplier, bar.start_at): bar for bar in self.minute_agg_bars}
        for bar in bars:
            merged[(bar.multiplier, bar.start_at)] = bar
        self.minute_agg_bars = sorted(merged.values(), key=lambda bar: (bar.multiplier, bar.start_at))

    async def list_minute_tickers(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[str]:
        _ = (start_at, end_at)
        symbols = sorted({bar.ticker for bar in self.minute_bars})
        return symbols

    async def list_recent_minute_trade_dates(self, *, limit: int) -> list[date]:
        if self.minute_trade_dates:
            ordered = sorted(set(self.minute_trade_dates), reverse=True)
            return ordered[:limit]
        ordered = sorted({bar.start_at.date() for bar in self.minute_bars}, reverse=True)
        return ordered[:limit]

    async def list_recent_minute_agg_trade_dates(self, *, limit: int) -> list[date]:
        if self.minute_agg_trade_dates:
            ordered = sorted(set(self.minute_agg_trade_dates), reverse=True)
            return ordered[:limit]
        ordered = sorted({bar.start_at.date() for bar in self.minute_agg_bars}, reverse=True)
        return ordered[:limit]

    async def delete_minute_bars_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        self.deleted_minute_cutoff = keep_from_trade_date
        return self.minute_delete_return

    async def delete_minute_agg_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        self.deleted_minute_agg_cutoff = keep_from_trade_date
        return self.minute_agg_delete_return


class FakeUoW:
    def __init__(self, *, market_data_repo: FakeMarketDataRepository) -> None:
        self.market_data_repo = market_data_repo
        self.auth_repo = None
        self.watchlist_repo = None
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class NoRefreshTradingCalendar:
    async def ensure_holiday_cache(self) -> None:
        return None

    def is_trading_day(self, *, target_date: date) -> bool:
        _ = target_date
        return False

    def session_bounds(self, *, target_date: date):
        _ = target_date
        return None

    def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
        _ = trading_days
        return target_date

    def count_session_minutes(self, *, start_date: date, end_date: date, max_minutes: int | None = None) -> int:
        estimated = max(0, (end_date - start_date).days + 1) * 390
        if max_minutes is not None:
            return min(estimated, max_minutes)
        return estimated

    def count_trading_days(self, *, start_date: date, end_date: date, max_count: int | None = None) -> int:
        estimated = max(0, (end_date - start_date).days + 1)
        if max_count is not None:
            return min(estimated, max_count)
        return estimated


class FakeMassiveClient:
    def __init__(self, payload_by_key: dict[tuple[str, int], list[dict]]) -> None:
        self.payload_by_key = payload_by_key
        self.calls: list[tuple[str, int]] = []
        self.requests: list[tuple[str, int, str, str]] = []

    async def list_aggs(
        self,
        *,
        ticker: str,
        multiplier: int,
        timespan: str,
        from_date: str,
        to_date: str,
        adjusted: bool = True,
        sort: str = "asc",
        limit: int = 50000,
    ) -> list[dict]:
        _ = (ticker, adjusted, sort, limit)
        self.calls.append((timespan, multiplier))
        self.requests.append((timespan, multiplier, from_date, to_date))
        return self.payload_by_key.get((timespan, multiplier), [])

    async def list_market_holidays(self) -> list[dict]:
        return []


class FailMassiveClient:
    async def list_aggs(
        self,
        *,
        ticker: str,
        multiplier: int,
        timespan: str,
        from_date: str,
        to_date: str,
        adjusted: bool = True,
        sort: str = "asc",
        limit: int = 50000,
    ) -> list[dict]:
        _ = (ticker, multiplier, timespan, from_date, to_date, adjusted, sort, limit)
        raise AssertionError("Massive client should not be called")

    async def list_market_holidays(self) -> list[dict]:
        return []


class UnavailableMassiveClient:
    async def list_aggs(
        self,
        *,
        ticker: str,
        multiplier: int,
        timespan: str,
        from_date: str,
        to_date: str,
        adjusted: bool = True,
        sort: str = "asc",
        limit: int = 50000,
    ) -> list[dict]:
        _ = (ticker, multiplier, timespan, from_date, to_date, adjusted, sort, limit)
        raise ValueError("MARKET_DATA_UPSTREAM_UNAVAILABLE")

    async def list_market_holidays(self) -> list[dict]:
        return []


async def test_list_day_bars_reads_cached_baseline_without_upstream_refresh() -> None:
    repo = FakeMarketDataRepository()
    repo.day_bars = [
        _bar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        ),
        _bar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
            close=101.0,
        ),
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    result = await service.list_bars(
        ticker="aapl",
        timespan="day",
        multiplier=1,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 3),
    )

    assert len(result) == 2
    assert all(bar.ticker == "AAPL" for bar in result)


async def test_list_day_baseline_returns_cached_bars_when_refresh_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)  # 10:00 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.day_bars = [
        _bar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
            close=101.0,
            is_final=True,
        )
    ]
    uow = FakeUoW(market_data_repo=repo)
    service = MarketDataApplicationService(
        uow=uow,
        massive_client=UnavailableMassiveClient(),
    )

    result = await service.list_bars(
        ticker="AAPL",
        timespan="day",
        multiplier=1,
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert [bar.start_at for bar in result] == [datetime(2026, 2, 10, tzinfo=timezone.utc)]
    assert result[0].close == 101.0
    assert uow.commits == 0


async def test_list_day_baseline_keeps_same_trade_date_non_final_until_next_trading_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 20, 21, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    class TwoDayTradingCalendar:
        async def ensure_holiday_cache(self) -> None:
            return None

        def is_trading_day(self, *, target_date: date) -> bool:
            return target_date in {date(2026, 2, 20), date(2026, 2, 23)}

        def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
            if target_date == date(2026, 2, 20) and trading_days == 1:
                return date(2026, 2, 23)
            return target_date

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    massive = FakeMassiveClient(
        {
            ("day", 1): [
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 20, tzinfo=timezone.utc)),
                    "o": 100,
                    "h": 102,
                    "l": 99,
                    "c": 101,
                    "v": 1000,
                }
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
        trading_calendar=TwoDayTradingCalendar(),  # type: ignore[arg-type]
    )

    result = await service.list_bars(
        ticker="AAPL",
        timespan="day",
        multiplier=1,
        start_date=date(2026, 2, 20),
        end_date=date(2026, 2, 20),
    )

    assert massive.requests == [("day", 1, "2026-02-20", "2026-02-20")]
    assert result[0].is_final is False
    assert repo.day_bars[0].is_final is False


async def test_list_day_baseline_promotes_day_bar_after_next_trading_day_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 23, 15, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    class TwoDayTradingCalendar:
        async def ensure_holiday_cache(self) -> None:
            return None

        def is_trading_day(self, *, target_date: date) -> bool:
            return target_date in {date(2026, 2, 20), date(2026, 2, 23)}

        def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
            if target_date == date(2026, 2, 20) and trading_days == 1:
                return date(2026, 2, 23)
            return target_date

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.day_bars = [
        _bar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
            close=100.5,
            is_final=False,
        )
    ]
    massive = FakeMassiveClient(
        {
            ("day", 1): [
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 20, tzinfo=timezone.utc)),
                    "o": 100,
                    "h": 102,
                    "l": 99,
                    "c": 101,
                    "v": 1000,
                }
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
        trading_calendar=TwoDayTradingCalendar(),  # type: ignore[arg-type]
    )

    result = await service.list_bars(
        ticker="AAPL",
        timespan="day",
        multiplier=1,
        start_date=date(2026, 2, 20),
        end_date=date(2026, 2, 20),
    )

    assert massive.requests == [("day", 1, "2026-02-20", "2026-02-20")]
    assert result[0].close == 101.0
    assert result[0].is_final is True
    assert repo.day_bars[0].is_final is True


async def test_list_minute_baseline_fetches_massive_when_missing() -> None:
    repo = FakeMarketDataRepository()
    massive = FakeMassiveClient(
        {
                (
                    "minute",
                    1,
                ): [
                    {
                        "t": 1704205800000,  # 2024-01-02T14:30:00Z (09:30 ET)
                        "o": 10,
                        "h": 12,
                        "l": 9,
                        "c": 11,
                    "v": 1000,
                }
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
    )

    result = await service.list_bars(
        ticker="MSFT",
        timespan="minute",
        multiplier=1,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 2),
    )

    assert massive.calls == [("minute", 1)]
    assert len(repo.upserted_minute) == 1
    assert result[0].ticker == "MSFT"


async def test_list_minute_baseline_keeps_recent_bar_non_final_until_delay_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2024, 1, 3, 15, 3, tzinfo=timezone.utc)  # 10:03 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    class CurrentDayOnlyTradingCalendar:
        async def ensure_holiday_cache(self) -> None:
            return None

        def is_trading_day(self, *, target_date: date) -> bool:
            return target_date == date(2024, 1, 3)

        def session_bounds(self, *, target_date: date):
            return (
                datetime.combine(target_date, time(9, 30), tzinfo=_MARKET_TZ),
                datetime.combine(target_date, time(16, 0), tzinfo=_MARKET_TZ),
            )

        def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
            _ = trading_days
            return target_date

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(
            ticker="MSFT",
            start_at=datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc),
            close=100.0,
            is_final=False,
        ),
    ]
    massive = FakeMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc)),
                    "o": 100,
                    "h": 101,
                    "l": 99.8,
                    "c": 100.8,
                    "v": 800,
                },
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 15, 3, tzinfo=timezone.utc)),
                    "o": 100.8,
                    "h": 101.1,
                    "l": 100.7,
                    "c": 101.0,
                    "v": 120,
                },
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
        trading_calendar=CurrentDayOnlyTradingCalendar(),  # type: ignore[arg-type]
    )

    result = await service.list_bars(
        ticker="MSFT",
        timespan="minute",
        multiplier=1,
        start_date=date(2024, 1, 3),
        end_date=date(2024, 1, 3),
    )

    assert result[0].start_at == datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc)
    assert result[0].is_final is False
    assert repo.minute_bars[0].is_final is False


async def test_list_minute_baseline_returns_cached_bars_when_refresh_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 10, 5, 2, tzinfo=timezone.utc)  # 00:02 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(
            ticker="MSFT",
            start_at=datetime(2026, 2, 10, 5, 0, tzinfo=timezone.utc),
            close=100.0,
            is_final=True,
        ),
        _bar(
            ticker="MSFT",
            start_at=datetime(2026, 2, 10, 5, 1, tzinfo=timezone.utc),
            close=100.6,
            is_final=True,
        ),
    ]
    uow = FakeUoW(market_data_repo=repo)
    service = MarketDataApplicationService(
        uow=uow,
        massive_client=UnavailableMassiveClient(),
    )

    result = await service.list_bars(
        ticker="MSFT",
        timespan="minute",
        multiplier=1,
        session="night",
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert [bar.start_at for bar in result] == [
        datetime(2026, 2, 10, 5, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 5, 1, tzinfo=timezone.utc),
    ]
    assert uow.commits == 0


async def test_list_day_baseline_raises_when_refresh_fails_and_cache_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.day_bars = [
        _bar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
            is_final=True,
        )
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=UnavailableMassiveClient(),
    )

    with pytest.raises(MarketDataUpstreamUnavailableError):
        await service.list_bars(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 11),
        )


async def test_list_minute_baseline_raises_when_refresh_fails_and_cache_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc)  # 10:05 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(
            ticker="MSFT",
            start_at=datetime(2026, 2, 10, 14, 30, tzinfo=timezone.utc),
            close=100.0,
            is_final=True,
        ),
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=UnavailableMassiveClient(),
    )

    with pytest.raises(MarketDataUpstreamUnavailableError):
        await service.list_bars(
            ticker="MSFT",
            timespan="minute",
            multiplier=1,
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 10),
        )


async def test_list_minute_baseline_refreshes_only_non_final_trade_date(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2024, 1, 3, 15, 5, tzinfo=timezone.utc)  # 10:05 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    class CurrentDayOnlyTradingCalendar:
        async def ensure_holiday_cache(self) -> None:
            return None

        def is_trading_day(self, *, target_date: date) -> bool:
            return target_date == date(2024, 1, 3)

        def session_bounds(self, *, target_date: date):
            return (
                datetime.combine(target_date, time(9, 30), tzinfo=_MARKET_TZ),
                datetime.combine(target_date, time(16, 0), tzinfo=_MARKET_TZ),
            )

        def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
            _ = trading_days
            return target_date

    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(
            ticker="MSFT",
            start_at=datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
            close=99.5,
            is_final=True,
        ),
        _bar(
            ticker="MSFT",
            start_at=datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc),
            close=100.0,
            is_final=False,
        ),
    ]
    massive = FakeMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc)),
                    "o": 100,
                    "h": 101,
                    "l": 99.8,
                    "c": 100.8,
                    "v": 800,
                },
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 15, 5, tzinfo=timezone.utc)),
                    "o": 100.8,
                    "h": 101.1,
                    "l": 100.7,
                    "c": 101.0,
                    "v": 120,
                },
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
        trading_calendar=CurrentDayOnlyTradingCalendar(),  # type: ignore[arg-type]
    )

    result = await service.list_bars(
        ticker="MSFT",
        timespan="minute",
        multiplier=1,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 3),
    )

    assert massive.requests == [("minute", 1, "2024-01-03", "2024-01-03")]
    assert [bar.start_at for bar in result] == [
        datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
        datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 3, 15, 5, tzinfo=timezone.utc),
    ]
    assert repo.minute_bars[1].close == 100.8
    assert repo.minute_bars[1].is_final is True
    assert repo.minute_bars[2].start_at == datetime(2024, 1, 3, 15, 5, tzinfo=timezone.utc)
    assert repo.minute_bars[2].is_final is False


async def test_list_minute_baseline_refreshes_closed_trade_date_when_final_cache_has_gaps() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(
            ticker="MSFT",
            start_at=datetime(2024, 1, 3, 14, 30, tzinfo=timezone.utc),
            close=100.0,
            is_final=True,
        )
    ]
    massive = FakeMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 14, 30, tzinfo=timezone.utc)),
                    "o": 100.0,
                    "h": 100.5,
                    "l": 99.8,
                    "c": 100.2,
                    "v": 800,
                },
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 14, 31, tzinfo=timezone.utc)),
                    "o": 100.2,
                    "h": 100.7,
                    "l": 100.1,
                    "c": 100.6,
                    "v": 500,
                },
            ]
        }
    )
    uow = FakeUoW(market_data_repo=repo)
    service = MarketDataApplicationService(
        uow=uow,
        massive_client=massive,
    )

    result = await service.list_bars(
        ticker="MSFT",
        timespan="minute",
        multiplier=1,
        start_date=date(2024, 1, 3),
        end_date=date(2024, 1, 3),
    )

    assert massive.requests == [("minute", 1, "2024-01-03", "2024-01-03")]
    assert [bar.start_at for bar in result] == [
        datetime(2024, 1, 3, 14, 30, tzinfo=timezone.utc),
        datetime(2024, 1, 3, 14, 31, tzinfo=timezone.utc),
    ]
    assert uow.commits == 1


async def test_list_minute_baseline_non_regular_refreshes_when_trade_date_is_not_final() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc), is_final=False),
    ]
    massive = FakeMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc)),
                    "o": 100,
                    "h": 101,
                    "l": 99,
                    "c": 100.5,
                    "v": 1000,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 22, 1, tzinfo=timezone.utc)),
                    "o": 100.5,
                    "h": 101.2,
                    "l": 100.1,
                    "c": 101,
                    "v": 900,
                },
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
    )

    bars = await service.list_bars(
        ticker="AAPL",
        timespan="minute",
        multiplier=1,
        session="night",
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert massive.calls == [("minute", 1)]
    assert [bar.start_at for bar in bars] == [
        datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 22, 1, tzinfo=timezone.utc),
    ]


async def test_list_minute_baseline_night_session_uses_time_aware_completeness(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)  # 10:00 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(
            ticker="AAPL",
            start_at=datetime(2026, 2, 10, 5, 0, tzinfo=timezone.utc) + timedelta(minutes=offset),
            is_final=True,
        )
        for offset in range(240)
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    bars = await service.list_bars(
        ticker="AAPL",
        timespan="minute",
        multiplier=1,
        session="night",
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert len(bars) == 240


async def test_list_minute_baseline_coalesces_concurrent_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2024, 1, 3, 15, 5, tzinfo=timezone.utc)  # 10:05 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    class CurrentDayOnlyTradingCalendar:
        async def ensure_holiday_cache(self) -> None:
            return None

        def is_trading_day(self, *, target_date: date) -> bool:
            return target_date == date(2024, 1, 3)

        def session_bounds(self, *, target_date: date):
            return (
                datetime.combine(target_date, time(9, 30), tzinfo=_MARKET_TZ),
                datetime.combine(target_date, time(16, 0), tzinfo=_MARKET_TZ),
            )

        def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
            _ = trading_days
            return target_date

    class SlowMassiveClient(FakeMassiveClient):
        async def list_aggs(self, **kwargs) -> list[dict]:
            await asyncio.sleep(0.01)
            return await super().list_aggs(**kwargs)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    uow = FakeUoW(market_data_repo=repo)
    massive = SlowMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc)),
                    "o": 100,
                    "h": 101,
                    "l": 99.8,
                    "c": 100.8,
                    "v": 800,
                }
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=uow,
        massive_client=massive,
        trading_calendar=CurrentDayOnlyTradingCalendar(),  # type: ignore[arg-type]
    )

    first, second = await asyncio.gather(
        service.list_bars(
            ticker="MSFT",
            timespan="minute",
            multiplier=1,
            start_date=date(2024, 1, 3),
            end_date=date(2024, 1, 3),
        ),
        service.list_bars(
            ticker="MSFT",
            timespan="minute",
            multiplier=1,
            start_date=date(2024, 1, 3),
            end_date=date(2024, 1, 3),
        ),
    )

    assert len(first) == 1
    assert len(second) == 1
    assert massive.requests == [("minute", 1, "2024-01-03", "2024-01-03")]
    assert uow.commits == 1


async def test_list_minute_baseline_cancellation_does_not_abort_shared_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2024, 1, 3, 15, 5, tzinfo=timezone.utc)  # 10:05 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    class CurrentDayOnlyTradingCalendar:
        async def ensure_holiday_cache(self) -> None:
            return None

        def is_trading_day(self, *, target_date: date) -> bool:
            return target_date == date(2024, 1, 3)

        def session_bounds(self, *, target_date: date):
            return (
                datetime.combine(target_date, time(9, 30), tzinfo=_MARKET_TZ),
                datetime.combine(target_date, time(16, 0), tzinfo=_MARKET_TZ),
            )

        def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
            _ = trading_days
            return target_date

    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingMassiveClient(FakeMassiveClient):
        async def list_aggs(self, **kwargs) -> list[dict]:
            started.set()
            await release.wait()
            return await super().list_aggs(**kwargs)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    uow = FakeUoW(market_data_repo=repo)
    massive = BlockingMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2024, 1, 3, 15, 0, tzinfo=timezone.utc)),
                    "o": 100,
                    "h": 101,
                    "l": 99.8,
                    "c": 100.8,
                    "v": 800,
                }
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=uow,
        massive_client=massive,
        trading_calendar=CurrentDayOnlyTradingCalendar(),  # type: ignore[arg-type]
    )

    first_task = asyncio.create_task(
        service.list_bars(
            ticker="MSFT",
            timespan="minute",
            multiplier=1,
            start_date=date(2024, 1, 3),
            end_date=date(2024, 1, 3),
        )
    )
    await started.wait()

    second_task = asyncio.create_task(
        service.list_bars(
            ticker="MSFT",
            timespan="minute",
            multiplier=1,
            start_date=date(2024, 1, 3),
            end_date=date(2024, 1, 3),
        )
    )
    await asyncio.sleep(0)

    first_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first_task

    release.set()
    second = await second_task
    await asyncio.sleep(0)

    assert len(second) == 1
    assert massive.requests == [("minute", 1, "2024-01-03", "2024-01-03")]
    assert uow.commits == 1
    assert service._baseline_refresh_tasks == {}


async def test_list_minute_aggregated_returns_db_agg_mixed_for_open_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 2, 10, 15, 7, tzinfo=timezone.utc)  # 10:07 ET

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.minute_coverage = (
        datetime(2026, 2, 10, 14, 30, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 20, 59, tzinfo=timezone.utc),
    )
    repo.minute_agg_bars = [
        _bar(
            ticker="AAPL",
            timespan="minute",
            multiplier=5,
            start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc),
            is_final=True,
            source="DB_AGG",
        )
    ]
    repo.minute_bars = [
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc)),
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 6, tzinfo=timezone.utc), close=101.2),
    ]

    massive = FakeMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc)),
                    "o": 100.0,
                    "h": 100.8,
                    "l": 99.8,
                    "c": 100.4,
                    "v": 900,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 15, 6, tzinfo=timezone.utc)),
                    "o": 100.4,
                    "h": 101.3,
                    "l": 100.2,
                    "c": 101.2,
                    "v": 950,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 15, 7, tzinfo=timezone.utc)),
                    "o": 101.2,
                    "h": 101.4,
                    "l": 101.0,
                    "c": 101.3,
                    "v": 400,
                },
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
    )

    result = await service.list_bars_with_meta(
        ticker="AAPL",
        timespan="minute",
        multiplier=5,
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert result.data_source == "DB_AGG_MIXED"
    assert len(result.bars) == 2
    assert result.bars[0].start_at == datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)
    assert result.bars[1].start_at == datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc)
    assert result.bars[1].is_final is False
    assert massive.requests == [("minute", 1, "2026-02-10", "2026-02-10")]


async def test_list_minute_aggregated_rebuilds_from_baseline_when_preagg_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc)  # 17:00 ET, no open bucket

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(market_data_service_module, "datetime", FixedDateTime)

    repo = FakeMarketDataRepository()
    repo.minute_coverage = (
        datetime(2026, 2, 10, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 21, 0, tzinfo=timezone.utc),
    )
    massive = FakeMassiveClient(
        {
            ("minute", 1): [
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 20, 55, tzinfo=timezone.utc)),
                    "o": 200,
                    "h": 201,
                    "l": 199,
                    "c": 200.2,
                    "v": 300,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 20, 56, tzinfo=timezone.utc)),
                    "o": 200.2,
                    "h": 201.2,
                    "l": 200.1,
                    "c": 200.8,
                    "v": 250,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 20, 57, tzinfo=timezone.utc)),
                    "o": 200.8,
                    "h": 201.0,
                    "l": 200.5,
                    "c": 200.9,
                    "v": 220,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 20, 58, tzinfo=timezone.utc)),
                    "o": 200.9,
                    "h": 201.4,
                    "l": 200.8,
                    "c": 201.1,
                    "v": 180,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 20, 59, tzinfo=timezone.utc)),
                    "o": 201.1,
                    "h": 201.5,
                    "l": 201.0,
                    "c": 201.3,
                    "v": 250,
                }
            ]
        }
    )
    service = MarketDataApplicationService(uow=FakeUoW(market_data_repo=repo), massive_client=massive)

    result = await service.list_bars_with_meta(
        ticker="AAPL",
        timespan="minute",
        multiplier=5,
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert result.data_source == "DB_AGG"
    assert len(result.bars) == 1
    assert result.bars[0].start_at == datetime(2026, 2, 10, 20, 55, tzinfo=timezone.utc)
    assert massive.requests == [("minute", 1, "2026-02-10", "2026-02-10")]
    assert len(repo.upserted_minute_agg) == 1


async def test_list_minute_aggregated_night_fallback_clips_out_of_range_bars() -> None:
    repo = FakeMarketDataRepository()
    massive = FakeMassiveClient(
        {
            ("minute", 5): [
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 9, 6, 30, tzinfo=timezone.utc)),  # 01:30 ET (prev day)
                    "o": 90,
                    "h": 91,
                    "l": 89.5,
                    "c": 90.2,
                    "v": 500,
                },
                {
                    "t": _to_epoch_millis(datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc)),  # 17:00 ET
                    "o": 100,
                    "h": 102,
                    "l": 99.5,
                    "c": 101,
                    "v": 1200,
                },
            ]
        }
    )
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=massive,
    )

    result = await service.list_bars_with_meta(
        ticker="AAPL",
        timespan="minute",
        multiplier=5,
        session="night",
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert result.data_source == "REST"
    assert [bar.start_at for bar in result.bars] == [datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc)]


async def test_precompute_minute_aggregates_only_writes_final_buckets() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_bars = [
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc), close=100.0),
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 1, tzinfo=timezone.utc), close=101.0),
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 2, tzinfo=timezone.utc), close=102.0),
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 3, tzinfo=timezone.utc), close=103.0),
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 4, tzinfo=timezone.utc), close=104.0),
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc), close=105.0),
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 6, tzinfo=timezone.utc), close=106.0),
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    produced = await service.precompute_minute_aggregates(
        multiplier=5,
        lookback_trade_days=1,
        now=datetime(2026, 2, 10, 15, 7, tzinfo=timezone.utc),
    )

    assert produced == 1
    assert len(repo.upserted_minute_agg) == 1
    assert repo.upserted_minute_agg[0].start_at == datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)
    assert repo.upserted_minute_agg[0].end_at == datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc)


async def test_enforce_minute_retention_uses_trade_day_cutoff() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_trade_dates = [
        date(2026, 2, 17),
        date(2026, 2, 16),
        date(2026, 2, 13),
        date(2026, 2, 12),
    ]
    repo.minute_agg_trade_dates = list(repo.minute_trade_dates)
    repo.minute_delete_return = 12
    repo.minute_agg_delete_return = 6
    uow = FakeUoW(market_data_repo=repo)
    service = MarketDataApplicationService(
        uow=uow,
        massive_client=FailMassiveClient(),
    )

    result = await service.enforce_minute_retention(keep_trade_days=3)

    assert result == {"minute_deleted": 12, "minute_agg_deleted": 6}
    assert repo.deleted_minute_cutoff == date(2026, 2, 13)
    assert repo.deleted_minute_agg_cutoff == date(2026, 2, 13)
    assert uow.commits == 1


async def test_enforce_minute_retention_skips_delete_when_trade_days_insufficient() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_trade_dates = [date(2026, 2, 17), date(2026, 2, 16)]
    repo.minute_agg_trade_dates = [date(2026, 2, 17), date(2026, 2, 16)]
    uow = FakeUoW(market_data_repo=repo)
    service = MarketDataApplicationService(
        uow=uow,
        massive_client=FailMassiveClient(),
    )

    result = await service.enforce_minute_retention(keep_trade_days=3)

    assert result == {"minute_deleted": 0, "minute_agg_deleted": 0}
    assert repo.deleted_minute_cutoff is None
    assert repo.deleted_minute_agg_cutoff is None
    assert uow.commits == 0


async def test_list_bars_rejects_oversized_range_when_only_start_date_is_provided() -> None:
    repo = FakeMarketDataRepository()
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    with pytest.raises(MarketDataRangeTooLargeError):
        await service.list_bars(
            ticker="AAPL",
            timespan="minute",
            multiplier=1,
            start_date=date(2000, 1, 1),
            end_date=None,
            enforce_range_limit=True,
        )


async def test_list_bars_allows_default_minute_range_without_explicit_bounds() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_coverage = (
        datetime(2000, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    repo.minute_bars = [
        _bar(
            ticker="AAPL",
            timespan="minute",
            multiplier=1,
            start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc),
        )
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    bars = await service.list_bars(
        ticker="AAPL",
        timespan="minute",
        multiplier=1,
        start_date=None,
        end_date=None,
        enforce_range_limit=True,
    )

    assert isinstance(bars, list)


async def test_list_bars_allows_to_only_minute_range_with_default_start() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_coverage = (
        datetime(2000, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    repo.minute_bars = [
        _bar(
            ticker="AAPL",
            timespan="minute",
            multiplier=1,
            start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc),
        )
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    bars = await service.list_bars(
        ticker="AAPL",
        timespan="minute",
        multiplier=1,
        start_date=None,
        end_date=date(2026, 2, 10),
        enforce_range_limit=True,
    )

    assert isinstance(bars, list)


async def test_list_minute_bars_filters_pre_session() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_coverage = (
        datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 23, 59, 59, tzinfo=timezone.utc),
    )
    repo.minute_bars = [
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 13, 15, tzinfo=timezone.utc)),  # 08:15 ET
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)),  # 10:00 ET
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc)),  # 17:00 ET
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    bars = await service.list_bars(
        ticker="AAPL",
        timespan="minute",
        multiplier=1,
        session="pre",
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert len(bars) == 1
    assert bars[0].start_at == datetime(2026, 2, 10, 13, 15, tzinfo=timezone.utc)


async def test_list_minute_bars_filters_night_session() -> None:
    repo = FakeMarketDataRepository()
    repo.minute_coverage = (
        datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 11, 4, 59, 59, 999999, tzinfo=timezone.utc),
    )
    repo.minute_bars = [
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 6, 30, tzinfo=timezone.utc)),  # 01:30 ET
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 13, 15, tzinfo=timezone.utc)),  # 08:15 ET
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)),  # 10:00 ET
        _bar(ticker="AAPL", start_at=datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc)),  # 17:00 ET
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    bars = await service.list_bars(
        ticker="AAPL",
        timespan="minute",
        multiplier=1,
        session="night",
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert len(bars) == 2
    assert [bar.start_at for bar in bars] == [
        datetime(2026, 2, 10, 6, 30, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc),
    ]


async def test_prefetch_default_does_not_apply_request_range_limit() -> None:
    repo = FakeMarketDataRepository()
    repo.day_coverage = (
        datetime(2000, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    repo.minute_coverage = (
        datetime(2000, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    repo.day_bars = [
        _bar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
        )
    ]
    repo.minute_bars = [
        _bar(
            ticker="AAPL",
            timespan="minute",
            multiplier=1,
            start_at=datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc),
        )
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
        trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
    )

    await service.prefetch_default(ticker="AAPL")


async def test_list_trading_days_skips_weekend() -> None:
    repo = FakeMarketDataRepository()
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
    )

    days = await service.list_trading_days(
        end_date=date(2026, 2, 24),
        count=3,
    )

    assert days == [date(2026, 2, 20), date(2026, 2, 23), date(2026, 2, 24)]


def test_align_on_or_before_raises_when_calendar_never_matches() -> None:
    with pytest.raises(ValueError):
        market_data_service_module._align_on_or_before(
            target_date=date(2026, 2, 10),
            trading_calendar=NoRefreshTradingCalendar(),  # type: ignore[arg-type]
        )


def _filter_by_range(
    bars: list[MarketBar],
    *,
    ticker: str,
    start_at: datetime,
    end_at: datetime,
    limit: int | None,
    session: str | None = None,
) -> list[MarketBar]:
    items = [bar for bar in bars if bar.ticker == ticker and start_at <= bar.start_at <= end_at]
    if session is not None:
        items = [bar for bar in items if _is_session_match(bar=bar, session=session)]
    items.sort(key=lambda bar: bar.start_at)
    if limit and limit > 0:
        return items[:limit]
    return items


def _is_session_match(*, bar: MarketBar, session: str) -> bool:
    local_time = bar.start_at.astimezone(_MARKET_TZ).time()
    if session == "regular":
        return time(9, 30) <= local_time < time(16, 0)
    if session == "pre":
        return time(4, 0) <= local_time < time(9, 30)
    if session == "night":
        return local_time >= time(16, 0) or local_time < time(4, 0)
    return False
