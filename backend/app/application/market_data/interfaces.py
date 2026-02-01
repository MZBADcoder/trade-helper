from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.market_data.schemas import MarketBar


class MarketDataApplicationService(Protocol):
    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[MarketBar]: ...

    def prefetch_default(self, *, ticker: str) -> None: ...
