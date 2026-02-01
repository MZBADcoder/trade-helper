from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.market_data.schemas import MarketBar


class MarketDataRepository(Protocol):
    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]: ...

    def get_range_coverage(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
    ) -> tuple[datetime, datetime] | None: ...

    def upsert_bars(self, bars: list[MarketBar]) -> None: ...
