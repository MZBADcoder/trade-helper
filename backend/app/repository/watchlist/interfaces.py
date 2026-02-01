from __future__ import annotations

from typing import Protocol

from app.domain.watchlist.schemas import WatchlistItem


class WatchlistRepository(Protocol):
    def list_items(self) -> list[WatchlistItem]: ...

    def add_item(self, *, ticker: str) -> WatchlistItem: ...

    def remove_item(self, *, ticker: str) -> None: ...
