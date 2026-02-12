from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class OptionExpiration:
    date: str
    days_to_expiration: int
    contract_count: int


@dataclass(slots=True)
class OptionExpirationsResult:
    underlying: str
    expirations: list[OptionExpiration]
    source: str
    updated_at: datetime


@dataclass(slots=True)
class OptionChainItem:
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


@dataclass(slots=True)
class OptionChainResult:
    underlying: str
    expiration: str
    items: list[OptionChainItem]
    next_cursor: str | None


@dataclass(slots=True)
class OptionQuote:
    bid: float
    ask: float
    last: float
    updated_at: datetime


@dataclass(slots=True)
class OptionSession:
    open: float
    high: float
    low: float
    volume: int
    open_interest: int


@dataclass(slots=True)
class OptionGreeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


@dataclass(slots=True)
class OptionContract:
    option_ticker: str
    underlying: str
    expiration: str
    option_type: str
    strike: float
    multiplier: int
    quote: OptionQuote
    session: OptionSession
    greeks: OptionGreeks | None
    source: str
