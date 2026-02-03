from __future__ import annotations

from app.repository.watchlist.interfaces import WatchlistRepository
from app.domain.watchlist.schemas import WatchlistItem


class DefaultWatchlistService:
    def __init__(self, *, repository: WatchlistRepository | None = None) -> None:
        if repository is None:
            raise ValueError("repository is required")
        self._repository = repository

    def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        _validate_user_id(user_id=user_id)
        return self._repository.list_items(user_id=user_id)

    def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        _validate_user_id(user_id=user_id)
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")
        return self._repository.add_item(user_id=user_id, ticker=normalized)

    def remove_item(self, *, user_id: int, ticker: str) -> None:
        _validate_user_id(user_id=user_id)
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")
        self._repository.remove_item(user_id=user_id, ticker=normalized)


def _validate_user_id(*, user_id: int) -> None:
    if user_id < 1:
        raise ValueError("Invalid user id")
