from __future__ import annotations

from app.repository.watchlist.interfaces import WatchlistRepository


class SqlAlchemyWatchlistRepository(WatchlistRepository):
    def __init__(self, *, session: object | None = None) -> None:
        self._session = session

    def list_items(self) -> list[dict]:
        raise NotImplementedError("watchlist repository not implemented")

    def add_item(self, *, ticker: str) -> dict:
        raise NotImplementedError("watchlist repository not implemented")

    def remove_item(self, *, ticker: str) -> None:
        raise NotImplementedError("watchlist repository not implemented")
