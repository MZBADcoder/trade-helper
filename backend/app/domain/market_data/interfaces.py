from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.market_data.schemas import MarketBar


class MarketDataService(Protocol):
    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_date: date,
        end_date: date,
        limit: int | None = None,
    ) -> list[MarketBar]: ...

    def prefetch_default(self, *, ticker: str) -> None: ...
