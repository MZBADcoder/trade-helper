from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.domain.market_data.schemas import MarketBar
from app.domain.market_data.services import DefaultMarketDataService


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


class FakePolygonClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.called = False

    def get(self, path: str, params: dict | None = None) -> dict:
        _ = (path, params)
        self.called = True
        return self.payload


class FailPolygonClient:
    def get(self, path: str, params: dict | None = None) -> dict:
        _ = (path, params)
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
    service = DefaultMarketDataService(repository=repo, polygon_client=FailPolygonClient())

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
    payload = {
        "results": [
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
    }
    repo = FakeMarketDataRepository(bars=[], coverage=None)
    polygon = FakePolygonClient(payload)
    service = DefaultMarketDataService(repository=repo, polygon_client=polygon)

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
    service = DefaultMarketDataService(repository=repo, polygon_client=FailPolygonClient())

    with pytest.raises(ValueError):
        service.list_bars(
            ticker="AAPL",
            timespan="day",
            multiplier=1,
            start_date=date(2024, 1, 5),
            end_date=date(2024, 1, 4),
        )
