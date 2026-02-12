from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.application.market_data.service import DefaultMarketDataApplicationService
from app.domain.market_data.schemas import MarketBar


class FakeMarketDataRepository:
    def __init__(self, *, bars: list[MarketBar] | None = None, coverage=None) -> None:
        self._bars = bars or []
        self._coverage = coverage
        self.upserted: list[MarketBar] = []

    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]:
        _ = (ticker, timespan, multiplier, start_at, end_at, limit)
        return self._bars

    def get_range_coverage(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
    ):
        _ = (ticker, timespan, multiplier)
        return self._coverage

    def upsert_bars(self, bars: list[MarketBar]) -> None:
        self.upserted.extend(bars)
        self._bars = list(bars)


class FakeUoW:
    def __init__(self, *, market_data_repo: FakeMarketDataRepository) -> None:
        self.market_data_repo = market_data_repo
        self.auth_repo = None
        self.watchlist_repo = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class FakePolygonClient:
    def __init__(self, payload: list[dict]) -> None:
        self.payload = payload
        self.called = False

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
        self.called = True
        return self.payload


class FailPolygonClient:
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
        raise AssertionError("Polygon client should not be called")


def test_list_bars_uses_cache_when_coverage_sufficient() -> None:
    start = date(2024, 1, 1)
    end = date(2024, 1, 3)
    coverage = (
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 31, tzinfo=timezone.utc),
    )
    cached = [
        MarketBar(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=100,
            vwap=None,
            trades=None,
        )
    ]
    repo = FakeMarketDataRepository(bars=cached, coverage=coverage)
    service = DefaultMarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        polygon_client=FailPolygonClient(),
    )

    result = service.list_bars(
        ticker="aapl",
        timespan="day",
        multiplier=1,
        start_date=start,
        end_date=end,
    )

    assert result == cached
    assert repo.upserted == []


def test_list_bars_fetches_polygon_when_cache_missing() -> None:
    payload = [
        {
            "t": 1704153600000,
            "o": 10,
            "h": 12,
            "l": 9,
            "c": 11,
            "v": 1000,
            "vw": 10.5,
            "n": 50,
        }
    ]
    repo = FakeMarketDataRepository(bars=[], coverage=None)
    polygon = FakePolygonClient(payload)
    service = DefaultMarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        polygon_client=polygon,
    )

    result = service.list_bars(
        ticker="MSFT",
        timespan="day",
        multiplier=1,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 2),
    )

    assert polygon.called is True
    assert len(repo.upserted) == 1
    assert result == repo.upserted
    assert result[0].ticker == "MSFT"


def test_list_bars_rejects_invalid_date_range() -> None:
    repo = FakeMarketDataRepository(bars=[], coverage=None)
    service = DefaultMarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        polygon_client=FailPolygonClient(),
    )

    with pytest.raises(ValueError):
        service.list_bars(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_date=date(2024, 1, 5),
            end_date=date(2024, 1, 4),
        )


def test_prefetch_default_calls_list_bars_with_normalized_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeMarketDataRepository(bars=[], coverage=None)
    service = DefaultMarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        polygon_client=FailPolygonClient(),
    )
    captured: dict[str, object] = {}

    def fake_list_bars(
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[MarketBar]:
        captured.update(
            {
                "ticker": ticker,
                "timespan": timespan,
                "multiplier": multiplier,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            }
        )
        return []

    monkeypatch.setattr(service, "list_bars", fake_list_bars)

    service.prefetch_default(ticker=" aapl ")

    assert captured["ticker"] == "AAPL"
    assert captured["timespan"] == "day"
    assert captured["multiplier"] == 1
    assert captured["start_date"] is not None
    assert captured["end_date"] is not None
    assert captured["limit"] is None


def test_prefetch_default_rejects_blank_ticker() -> None:
    repo = FakeMarketDataRepository(bars=[], coverage=None)
    service = DefaultMarketDataApplicationService(
        uow=FakeUoW(market_data_repo=repo),
        polygon_client=FailPolygonClient(),
    )

    with pytest.raises(ValueError, match="Ticker is required"):
        service.prefetch_default(ticker="   ")
