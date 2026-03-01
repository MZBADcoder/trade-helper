from __future__ import annotations

import pytest

from app.application.watchlist.service import WatchlistApplicationService
from app.domain.watchlist.schemas import WatchlistItem


class FakeWatchlistRepository:
    def __init__(self) -> None:
        self.items: dict[str, WatchlistItem] = {}

    async def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        _ = user_id
        return list(self.items.values())

    async def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        _ = user_id
        item = WatchlistItem(ticker=ticker, created_at=None)
        self.items[ticker] = item
        return item

    async def remove_item(self, *, user_id: int, ticker: str) -> None:
        _ = user_id
        self.items.pop(ticker, None)


class FakeUoW:
    def __init__(self, *, watchlist_repo: FakeWatchlistRepository) -> None:
        self.watchlist_repo = watchlist_repo
        self.auth_repo = None
        self.market_data_repo = None
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self.rollback()
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeMarketDataService:
    def __init__(self) -> None:
        self.prefetched: list[str] = []

    async def prefetch_default(self, *, ticker: str) -> None:
        self.prefetched.append(ticker)


async def test_add_item_triggers_market_data_prefetch() -> None:
    repo = FakeWatchlistRepository()
    market_data = FakeMarketDataService()
    service = WatchlistApplicationService(
        uow=FakeUoW(watchlist_repo=repo),
        market_data_service=market_data,
    )

    item = await service.add_item(user_id=1, ticker="aapl")

    assert item.ticker == "AAPL"
    assert market_data.prefetched == ["AAPL"]


async def test_add_item_rejects_invalid_ticker_format() -> None:
    repo = FakeWatchlistRepository()
    service = WatchlistApplicationService(
        uow=FakeUoW(watchlist_repo=repo),
    )

    with pytest.raises(ValueError, match="Ticker format is invalid"):
        await service.add_item(user_id=1, ticker="AAPL;DROP")


async def test_remove_item_rejects_invalid_ticker_format() -> None:
    repo = FakeWatchlistRepository()
    service = WatchlistApplicationService(
        uow=FakeUoW(watchlist_repo=repo),
    )

    with pytest.raises(ValueError, match="Ticker format is invalid"):
        await service.remove_item(user_id=1, ticker="AAPL;DROP")
