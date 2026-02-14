from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.application.market_data.service import DefaultMarketDataApplicationService
from app.domain.market_data.schemas import MarketSnapshot


class FakeUoW:
    market_data_repo = None
    auth_repo = None
    watchlist_repo = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class FakeMassiveSnapshotClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.payload: list[dict] = [
            {
                "ticker": "AAPL",
                "last": 203.12,
                "change": -0.85,
                "change_pct": -0.42,
                "open": 204.01,
                "high": 205.30,
                "low": 201.98,
                "volume": 48923112,
                "updated_at": "2026-02-10T14:31:22Z",
                "market_status": "open",
                "source": "REST",
            }
        ]

    def list_snapshots(self, *, tickers: list[str]) -> list[dict]:
        self.calls.append(tickers)
        return list(self.payload)


class SnapshotDay:
    def __init__(self, *, open: float, high: float, low: float, volume: float) -> None:
        self.open = open
        self.high = high
        self.low = low
        self.volume = volume


class SnapshotLastTrade:
    def __init__(self, *, price: float) -> None:
        self.price = price


class SnapshotObject:
    def __init__(
        self,
        *,
        ticker: str,
        todays_change: float,
        todays_change_percent: float,
        updated: int,
        day: SnapshotDay,
        last_trade: SnapshotLastTrade,
    ) -> None:
        self.ticker = ticker
        self.todays_change = todays_change
        self.todays_change_percent = todays_change_percent
        self.updated = updated
        self.day = day
        self.last_trade = last_trade


def test_list_snapshots_raises_upstream_unavailable_when_client_missing() -> None:
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), massive_client=None)

    with pytest.raises(ValueError, match="MARKET_DATA_UPSTREAM_UNAVAILABLE"):
        service.list_snapshots(tickers=["AAPL"])


def test_list_snapshots_returns_mapped_domain_snapshots() -> None:
    client = FakeMassiveSnapshotClient()
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    result = service.list_snapshots(tickers=["aapl", "AAPL", "nvda"])

    assert client.calls == [["AAPL", "NVDA"]]
    assert len(result) == 1
    item = result[0]
    assert isinstance(item, MarketSnapshot)
    assert item.ticker == "AAPL"
    assert item.last == pytest.approx(203.12)
    assert item.change == pytest.approx(-0.85)
    assert item.change_pct == pytest.approx(-0.42)
    assert item.updated_at == datetime(2026, 2, 10, 14, 31, 22, tzinfo=timezone.utc)
    assert item.source == "REST"


def test_list_snapshots_rejects_invalid_ticker() -> None:
    client = FakeMassiveSnapshotClient()
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    with pytest.raises(ValueError, match="MARKET_DATA_INVALID_TICKERS"):
        service.list_snapshots(tickers=["AA-PL"])


def test_list_snapshots_rejects_too_many_unique_tickers() -> None:
    client = FakeMassiveSnapshotClient()
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), massive_client=client)
    tickers = [f"T{idx:02d}" for idx in range(51)]

    with pytest.raises(ValueError, match="MARKET_DATA_INVALID_TICKERS"):
        service.list_snapshots(tickers=tickers)


def test_list_snapshots_maps_rate_limit_error() -> None:
    class RateLimitedClient:
        def list_snapshots(self, *, tickers: list[str]) -> list[dict]:
            _ = tickers
            raise RuntimeError("429 rate limit exceeded")

    service = DefaultMarketDataApplicationService(uow=FakeUoW(), massive_client=RateLimitedClient())

    with pytest.raises(ValueError, match="MARKET_DATA_RATE_LIMITED"):
        service.list_snapshots(tickers=["AAPL"])


def test_list_snapshots_returns_empty_list_for_empty_payload() -> None:
    client = FakeMassiveSnapshotClient()
    client.payload = []
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    result = service.list_snapshots(tickers=["AAPL"])

    assert result == []


def test_list_snapshots_maps_massive_ticker_snapshot_shape() -> None:
    client = FakeMassiveSnapshotClient()
    client.payload = [
        SnapshotObject(
            ticker="AAPL",
            todays_change=-0.85,
            todays_change_percent=-0.42,
            updated=1707575482000,
            day=SnapshotDay(open=204.01, high=205.30, low=201.98, volume=48923112),
            last_trade=SnapshotLastTrade(price=203.12),
        )
    ]
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), massive_client=client)

    result = service.list_snapshots(tickers=["AAPL"])

    assert len(result) == 1
    item = result[0]
    assert item.ticker == "AAPL"
    assert item.last == pytest.approx(203.12)
    assert item.change == pytest.approx(-0.85)
    assert item.change_pct == pytest.approx(-0.42)
    assert item.open == pytest.approx(204.01)
    assert item.high == pytest.approx(205.30)
    assert item.low == pytest.approx(201.98)
    assert item.volume == 48923112
    assert item.updated_at == datetime(2024, 2, 10, 14, 31, 22, tzinfo=timezone.utc)
