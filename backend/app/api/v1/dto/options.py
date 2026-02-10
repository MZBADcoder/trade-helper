from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OptionExpirationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    date: str
    days_to_expiration: int
    contract_count: int


class OptionExpirationsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    underlying: str
    expirations: list[OptionExpirationOut]
    source: str
    updated_at: datetime


class OptionChainItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    option_ticker: str
    option_type: str
    strike: float
    bid: float
    ask: float
    last: float
    iv: float
    volume: int
    open_interest: int
    updated_at: datetime
    source: str


class OptionChainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    underlying: str
    expiration: str
    items: list[OptionChainItemOut]
    next_cursor: str | None = None


class OptionQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    bid: float
    ask: float
    last: float
    updated_at: datetime


class OptionSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    open: float
    high: float
    low: float
    volume: int
    open_interest: int


class OptionGreeksOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


class OptionContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    option_ticker: str
    underlying: str
    expiration: str
    option_type: str
    strike: float
    multiplier: int
    quote: OptionQuoteOut
    session: OptionSessionOut
    greeks: OptionGreeksOut | None = None
    source: str
