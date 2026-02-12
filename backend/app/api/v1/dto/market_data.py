from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MarketBarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

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


class MarketSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

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
    source: str


class MarketSnapshotsOut(BaseModel):
    items: list[MarketSnapshotOut]
