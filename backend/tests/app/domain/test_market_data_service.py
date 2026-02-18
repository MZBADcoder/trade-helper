from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.application.market_data import service as market_data_service_module
from app.application.market_data.service import MarketDataApplicationService
from app.domain.market_data.schemas import MarketBar


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
    is_final: bool | None = None,
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


class FakeMarketDataRepository:
    def __init__(self) -> None:
        self.day_bars: list[MarketBar] = []
        self.minute_bars: list[MarketBar] = []
        self.minute_agg_bars: list[MarketBar] = []

        self.day_coverage: tuple[datetime, datetime] | None = None
        self.minute_coverage: tuple[datetime, datetime] | None = None

        self.upserted_day: list[MarketBar] = []
        self.upserted_minute: list[MarketBar] = []
        self.upserted_minute_agg: list[MarketBar] = []

    def list_day_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]:
        return _filter_by_range(self.day_bars, ticker=ticker, start_at=start_at, end_at=end_at, limit=limit)

    def list_minute_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]:
        return _filter_by_range(self.minute_bars, ticker=ticker, start_at=start_at, end_at=end_at, limit=limit)

    def list_minute_agg_bars(
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

    def list_minute_bars_for_bucket(
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

    def get_day_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        _ = ticker
        return self.day_coverage

    def get_minute_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        _ = ticker
        return self.minute_coverage

    def upsert_day_bars(self, bars: list[MarketBar]) -> None:
        self.upserted_day.extend(bars)
        self.day_bars = sorted(bars, key=lambda bar: bar.start_at)

    def upsert_minute_bars(self, bars: list[MarketBar]) -> None:
        self.upserted_minute.extend(bars)
        self.minute_bars = sorted(bars, key=lambda bar: bar.start_at)

    def upsert_minute_agg_bars(self, bars: list[MarketBar]) -> None:
        self.upserted_minute_agg.extend(bars)
        self.minute_agg_bars = sorted(bars, key=lambda bar: bar.start_at)

    def list_minute_tickers(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[str]:
        _ = (start_at, end_at)
        symbols = sorted({bar.ticker for bar in self.minute_bars})
        return symbols

    def delete_minute_bars_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        _ = keep_from_trade_date
        return 0

    def delete_minute_agg_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        _ = keep_from_trade_date
        return 0


class FakeUoW:
    def __init__(self, *, market_data_repo: FakeMarketDataRepository) -> None:
        self.market_data_repo = market_data_repo
        self.auth_repo = None
        self.watchlist_repo = None
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None


class FakeMassiveClient:
    def __init__(self, payload_by_key: dict[tuple[str, int], list[dict]]) -> None:
        self.payload_by_key = payload_by_key
        self.calls: list[tuple[str, int]] = []

    def list_aggs(
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
        _ = (ticker, from_date, to_date, adjusted, sort, limit)
        self.calls.append((timespan, multiplier))
        return self.payload_by_key.get((timespan, multiplier), [])


class FailMassiveClient:
    def list_aggs(
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


def test_list_day_bars_reads_db_when_coverage_hit() -> None:
    repo = FakeMarketDataRepository()
    repo.day_coverage = (
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 31, tzinfo=timezone.utc),
    )
    repo.day_bars = [
        _bar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    ]
    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
    )

    result = service.list_bars(
        ticker="aapl",
        timespan="day",
        multiplier=1,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 3),
    )

    assert len(result) == 1
    assert result[0].ticker == "AAPL"


def test_list_minute_baseline_fetches_massive_when_missing() -> None:
    repo = FakeMarketDataRepository()
    massive = FakeMassiveClient(
        {
            (
                "minute",
                1,
            ): [
                {
                    "t": 1704188400000,  # 2024-01-02T09:00:00Z
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

    result = service.list_bars(
        ticker="MSFT",
        timespan="minute",
        multiplier=1,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 2),
    )

    assert massive.calls == [("minute", 1)]
    assert len(repo.upserted_minute) == 1
    assert result[0].ticker == "MSFT"


def test_list_minute_aggregated_returns_db_agg_mixed_for_open_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
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
        datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 23, 59, 59, 999999, tzinfo=timezone.utc),
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

    service = MarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        massive_client=FailMassiveClient(),
    )

    result = service.list_bars_with_meta(
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


def test_list_minute_aggregated_fallbacks_to_rest_when_preagg_empty(monkeypatch: pytest.MonkeyPatch) -> None:
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
            ("minute", 5): [
                {
                    "t": 1770735600000,
                    "o": 200,
                    "h": 201,
                    "l": 199,
                    "c": 200.5,
                    "v": 1200,
                }
            ]
        }
    )
    service = MarketDataApplicationService(uow=FakeUoW(market_data_repo=repo), massive_client=massive)

    result = service.list_bars_with_meta(
        ticker="AAPL",
        timespan="minute",
        multiplier=5,
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 10),
    )

    assert result.data_source == "REST"
    assert len(result.bars) == 1
    assert massive.calls[-1] == ("minute", 5)


def test_precompute_minute_aggregates_only_writes_final_buckets() -> None:
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
    )

    produced = service.precompute_minute_aggregates(
        multiplier=5,
        lookback_trade_days=1,
        now=datetime(2026, 2, 10, 15, 7, tzinfo=timezone.utc),
    )

    assert produced == 1
    assert len(repo.upserted_minute_agg) == 1
    assert repo.upserted_minute_agg[0].start_at == datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)
    assert repo.upserted_minute_agg[0].end_at == datetime(2026, 2, 10, 15, 5, tzinfo=timezone.utc)


def _filter_by_range(
    bars: list[MarketBar],
    *,
    ticker: str,
    start_at: datetime,
    end_at: datetime,
    limit: int | None,
) -> list[MarketBar]:
    items = [bar for bar in bars if bar.ticker == ticker and start_at <= bar.start_at <= end_at]
    items.sort(key=lambda bar: bar.start_at)
    if limit and limit > 0:
        return items[:limit]
    return items
