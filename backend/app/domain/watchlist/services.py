from __future__ import annotations

from app.repository.watchlist.interfaces import WatchlistRepository
from app.domain.watchlist.interfaces import WatchlistService


class DefaultWatchlistService(WatchlistService):
    def __init__(self, *, repository: WatchlistRepository | None = None) -> None:
        self._repository = repository

    def list_items(self) -> list[dict]:
        raise NotImplementedError("watchlist service not implemented")

    def add_item(self, *, ticker: str) -> dict:
        raise NotImplementedError("watchlist service not implemented")

    def remove_item(self, *, ticker: str) -> None:
        raise NotImplementedError("watchlist service not implemented")
