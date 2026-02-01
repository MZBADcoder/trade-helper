from __future__ import annotations

from typing import Protocol


class WatchlistApplicationService(Protocol):
    def list_items(self) -> list[dict]: ...

    def add_item(self, *, ticker: str) -> dict: ...

    def remove_item(self, *, ticker: str) -> None: ...
