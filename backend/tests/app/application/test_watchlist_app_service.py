from __future__ import annotations

from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.domain.watchlist.schemas import WatchlistItem


class FakeWatchlistRepository:
    def __init__(self) -> None:
        self.items: dict[str, WatchlistItem] = {}

    def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        _ = user_id
        return list(self.items.values())

    def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        _ = user_id
        item = WatchlistItem(ticker=ticker, created_at=None)
        self.items[ticker] = item
        return item

    def remove_item(self, *, user_id: int, ticker: str) -> None:
        _ = user_id
        self.items.pop(ticker, None)


class FakeMarketDataService:
    def __init__(self) -> None:
        self.prefetched: list[str] = []

    def prefetch_default(self, *, ticker: str) -> None:
        self.prefetched.append(ticker)


def test_add_item_triggers_market_data_prefetch() -> None:
    repo = FakeWatchlistRepository()
    market_data = FakeMarketDataService()
    service = DefaultWatchlistApplicationService(repository=repo, market_data_service=market_data)

    item = service.add_item(user_id=1, ticker="aapl")

    assert item.ticker == "AAPL"
    assert market_data.prefetched == ["AAPL"]
