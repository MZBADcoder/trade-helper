from __future__ import annotations

from typing import Protocol

from app.domain.watchlist.schemas import WatchlistItem


class WatchlistRepository(Protocol):
    def list_items(self, *, user_id: int) -> list[WatchlistItem]: ...

    def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem: ...

    def remove_item(self, *, user_id: int, ticker: str) -> None: ...
