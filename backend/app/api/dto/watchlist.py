from pydantic import BaseModel, Field


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


class WatchlistItemOut(BaseModel):
    ticker: str
    created_at: str | None = None

