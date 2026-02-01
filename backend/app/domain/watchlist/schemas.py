from pydantic import BaseModel, Field


class WatchlistItemIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


class WatchlistItem(BaseModel):
    ticker: str
    created_at: str | None = None
