from __future__ import annotations

from app.repository.watchlist.interfaces import WatchlistRepository
from app.domain.watchlist.interfaces import WatchlistService
from app.domain.watchlist.schemas import WatchlistItem


class DefaultWatchlistService(WatchlistService):
    def __init__(self, *, repository: WatchlistRepository | None = None) -> None:
        if repository is None:
            raise ValueError("repository is required")
        self._repository = repository

    def list_items(self) -> list[WatchlistItem]:
        return self._repository.list_items()

    def add_item(self, *, ticker: str) -> WatchlistItem:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")
        return self._repository.add_item(ticker=normalized)

    def remove_item(self, *, ticker: str) -> None:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")
        self._repository.remove_item(ticker=normalized)
