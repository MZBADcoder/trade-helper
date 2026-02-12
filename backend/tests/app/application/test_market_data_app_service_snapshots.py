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


class FakePolygonSnapshotClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def list_snapshots(self, *, tickers: list[str]) -> list[dict]:
        self.calls.append(tickers)
        return [
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


def test_list_snapshots_raises_upstream_unavailable_when_not_implemented() -> None:
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), polygon_client=None)

    with pytest.raises(ValueError, match="MARKET_DATA_UPSTREAM_UNAVAILABLE"):
        service.list_snapshots(tickers=["AAPL"])


@pytest.mark.xfail(reason="list_snapshots application behavior not implemented yet", strict=True)
def test_list_snapshots_returns_mapped_domain_snapshots() -> None:
    client = FakePolygonSnapshotClient()
    service = DefaultMarketDataApplicationService(uow=FakeUoW(), polygon_client=client)

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
