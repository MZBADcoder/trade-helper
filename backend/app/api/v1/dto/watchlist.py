from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    created_at: datetime | None = None


class WatchlistItemDeletedOut(BaseModel):
    deleted: str
