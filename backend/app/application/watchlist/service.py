from __future__ import annotations

from app.application.watchlist.interfaces import WatchlistApplicationService
from app.domain.watchlist.interfaces import WatchlistService


class DefaultWatchlistApplicationService(WatchlistApplicationService):
    def __init__(self, *, service: WatchlistService | None = None) -> None:
        self._service = service

    def list_items(self) -> list[dict]:
        raise NotImplementedError("watchlist application service not implemented")

    def add_item(self, *, ticker: str) -> dict:
        raise NotImplementedError("watchlist application service not implemented")

    def remove_item(self, *, ticker: str) -> None:
        raise NotImplementedError("watchlist application service not implemented")
