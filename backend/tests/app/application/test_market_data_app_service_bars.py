from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.application.market_data.service import MarketDataApplicationService
from app.domain.market_data.schemas import MarketBar


class FakeBarsRepo:
    def __init__(
        self,
        minute_bars: list[MarketBar],
        *,
        minute_agg_bars: list[MarketBar] | None = None,
        minute_agg_coverage: tuple[datetime, datetime] | None = None,
    ) -> None:
        self._minute_bars = minute_bars
        self._minute_agg_bars = list(minute_agg_bars or [])
        self._minute_agg_coverage = minute_agg_coverage
        self.upserted_agg_bars: list[MarketBar] = []
        self.list_minute_bars_calls = 0

    async def get_minute_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        _ = ticker
        return (
            datetime(2026, 2, 26, 14, 30, tzinfo=timezone.utc),
            datetime(2026, 2, 26, 20, 59, tzinfo=timezone.utc),
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
            for bar in self._minute_agg_bars
            if bar.ticker == ticker
            and bar.multiplier == multiplier
            and start_at <= bar.start_at <= end_at
            and (not final_only or bar.is_final is not False)
        ]
        items.sort(key=lambda bar: bar.start_at)
        if limit is not None and limit > 0:
            return items[:limit]
        return items

    async def get_minute_agg_range_coverage(
        self,
        *,
        ticker: str,
        multiplier: int,
    ) -> tuple[datetime, datetime] | None:
        _ = (ticker, multiplier)
        return self._minute_agg_coverage

    async def list_minute_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
        session: str | None = None,
    ) -> list[MarketBar]:
        _ = (ticker, limit, session)
        self.list_minute_bars_calls += 1
        return [bar for bar in self._minute_bars if start_at <= bar.start_at <= end_at]

    async def upsert_minute_agg_bars(self, bars: list[MarketBar]) -> None:
        self.upserted_agg_bars = list(bars)
        self._minute_agg_bars = list(bars)


class FakeBarsUoW:
    auth_repo = None
    watchlist_repo = None

    def __init__(self, repo: FakeBarsRepo) -> None:
        self.market_data_repo = repo
        self.commit_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        return None


class FakeBarsTradingCalendar:
    async def ensure_holiday_cache(self) -> None:
        return None

    def is_trading_day(self, *, target_date: date) -> bool:
        _ = target_date
        return False

    def shift_trading_day(self, *, target_date: date, trading_days: int) -> date:
        _ = trading_days
        return target_date


async def test_list_bars_minute_aggregation_rebuilds_from_minute_baseline_when_agg_cache_missing() -> None:
    minute_bars = [
        MarketBar(
            ticker="AMD",
            timespan="minute",
            multiplier=1,
            start_at=datetime(2026, 2, 26, 14, 30, tzinfo=timezone.utc),
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=1000,
            source="DB",
        ),
        MarketBar(
            ticker="AMD",
            timespan="minute",
            multiplier=1,
            start_at=datetime(2026, 2, 26, 15, 0, tzinfo=timezone.utc),
            open=100.5,
            high=101.5,
            low=100.2,
            close=101.2,
            volume=1200,
            source="DB",
        ),
        MarketBar(
            ticker="AMD",
            timespan="minute",
            multiplier=1,
            start_at=datetime(2026, 2, 26, 16, 30, tzinfo=timezone.utc),
            open=101.2,
            high=102.2,
            low=101.0,
            close=101.8,
            volume=900,
            source="DB",
        ),
    ]
    repo = FakeBarsRepo(minute_bars)
    uow = FakeBarsUoW(repo)
    service = MarketDataApplicationService(
        uow=uow,  # type: ignore[arg-type]
        massive_client=None,
        trading_calendar=FakeBarsTradingCalendar(),  # type: ignore[arg-type]
    )

    result = await service.list_bars_with_meta(
        ticker="AMD",
        timespan="minute",
        multiplier=60,
        session="regular",
        start_date=date(2026, 2, 26),
        end_date=date(2026, 2, 26),
        limit=500,
        enforce_range_limit=True,
    )

    assert len(result.bars) == 2
    assert [bar.start_at for bar in result.bars] == [
        datetime(2026, 2, 26, 14, 30, tzinfo=timezone.utc),
        datetime(2026, 2, 26, 16, 30, tzinfo=timezone.utc),
    ]
    assert result.data_source == "DB_AGG"
    assert len(repo.upserted_agg_bars) == 2
    assert uow.commit_calls == 1


async def test_list_bars_minute_aggregation_skips_rebuild_when_agg_coverage_has_last_bucket_start() -> None:
    bucket_starts = [
        datetime(2026, 2, 26, hour, 30, tzinfo=timezone.utc)
        for hour in (14, 15, 16, 17, 18, 19, 20)
    ]
    precomputed_agg = [
        MarketBar(
            ticker="AMD",
            timespan="minute",
            multiplier=60,
            start_at=start_at,
            end_at=min(start_at + timedelta(minutes=60), datetime(2026, 2, 26, 21, 0, tzinfo=timezone.utc)),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1000 + index,
            source="DB_AGG",
            is_final=True,
        )
        for index, start_at in enumerate(bucket_starts)
    ]

    repo = FakeBarsRepo(
        [],
        minute_agg_bars=precomputed_agg,
        minute_agg_coverage=(bucket_starts[0], bucket_starts[-1]),
    )
    uow = FakeBarsUoW(repo)
    service = MarketDataApplicationService(
        uow=uow,  # type: ignore[arg-type]
        massive_client=None,
        trading_calendar=FakeBarsTradingCalendar(),  # type: ignore[arg-type]
    )

    result = await service.list_bars_with_meta(
        ticker="AMD",
        timespan="minute",
        multiplier=60,
        session="regular",
        start_date=date(2026, 2, 26),
        end_date=date(2026, 2, 26),
        limit=500,
        enforce_range_limit=True,
    )

    assert len(result.bars) == len(precomputed_agg)
    assert [bar.start_at for bar in result.bars] == bucket_starts
    assert result.data_source == "DB_AGG"
    assert repo.upserted_agg_bars == []
    assert repo.list_minute_bars_calls == 0
    assert uow.commit_calls == 0
