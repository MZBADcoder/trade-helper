from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MarketBarOut(BaseModel):
    ticker: str
    timespan: str
    multiplier: int
    start_at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None
    trades: int | None = None
