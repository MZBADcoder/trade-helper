from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class WatchlistItem:
    ticker: str
    created_at: datetime | None = None
