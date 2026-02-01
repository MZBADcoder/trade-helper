from __future__ import annotations

from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str | None = None


class RuleOut(BaseModel):
    id: int
    key: str
    name: str | None = None
    created_at: str | None = None
