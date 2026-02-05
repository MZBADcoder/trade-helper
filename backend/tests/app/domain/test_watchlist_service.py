from __future__ import annotations

import pytest

from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.domain.watchlist.schemas import WatchlistItem


class FakeWatchlistRepository:
    def __init__(self) -> None:
        self.items_by_user: dict[int, list[WatchlistItem]] = {}
        self.last_add_call: tuple[int, str] | None = None
        self.last_remove_call: tuple[int, str] | None = None

    def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        return list(self.items_by_user.get(user_id, []))

    def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        self.last_add_call = (user_id, ticker)
        item = WatchlistItem(ticker=ticker, created_at=None)
        self.items_by_user.setdefault(user_id, []).append(item)
        return item

    def remove_item(self, *, user_id: int, ticker: str) -> None:
        self.last_remove_call = (user_id, ticker)
        self.items_by_user[user_id] = [
            item for item in self.items_by_user.get(user_id, []) if item.ticker != ticker
        ]


class FakeUoW:
    def __init__(self, *, watchlist_repo: FakeWatchlistRepository) -> None:
        self.watchlist_repo = watchlist_repo
        self.auth_repo = None
        self.market_data_repo = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_add_item_normalizes_ticker_and_user_scope() -> None:
    repo = FakeWatchlistRepository()
    service = DefaultWatchlistApplicationService(uow=FakeUoW(watchlist_repo=repo))

    created = service.add_item(user_id=7, ticker=" aapl ")

    assert created.ticker == "AAPL"
    assert repo.last_add_call == (7, "AAPL")


def test_list_items_rejects_invalid_user_id() -> None:
    repo = FakeWatchlistRepository()
    service = DefaultWatchlistApplicationService(uow=FakeUoW(watchlist_repo=repo))

    with pytest.raises(ValueError, match="Invalid user id"):
        service.list_items(user_id=0)


def test_remove_item_normalizes_ticker() -> None:
    repo = FakeWatchlistRepository()
    repo.items_by_user[3] = [WatchlistItem(ticker="MSFT", created_at=None)]
    service = DefaultWatchlistApplicationService(uow=FakeUoW(watchlist_repo=repo))

    service.remove_item(user_id=3, ticker=" msft ")

    assert repo.last_remove_call == (3, "MSFT")
    assert repo.items_by_user[3] == []
