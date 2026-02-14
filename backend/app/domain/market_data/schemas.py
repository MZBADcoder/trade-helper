from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MarketBar:
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
    source: str = "massive"


@dataclass(slots=True)
class MarketSnapshot:
    ticker: str
    last: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: int
    updated_at: datetime
    market_status: str
    source: str = "REST"
