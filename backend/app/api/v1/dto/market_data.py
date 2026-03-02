from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re

from fastapi import Query
from pydantic import BaseModel, ConfigDict

from app.api.errors import raise_api_error
from app.application.market_data.policy import (
    is_supported_timespan,
    is_valid_multiplier,
    normalize_timespan,
)

_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")
_OPTION_TICKER_PATTERN = re.compile(r"^O:[A-Z0-9]{1,32}$")
_SUPPORTED_SESSIONS = {"regular", "pre", "night"}


@dataclass(slots=True)
class MarketBarsRequest:
    symbol: str
    timespan: str
    multiplier: int
    session: str
    from_date: date | None
    to_date: date | None
    limit: int | None


@dataclass(slots=True)
class MarketSnapshotsRequest:
    tickers: list[str]


@dataclass(slots=True)
class MarketTradingDaysRequest:
    end_date: date | None
    count: int


def parse_market_bars_request(
    ticker: str | None = None,
    option_ticker: str | None = None,
    timespan: str = "day",
    multiplier: int = 1,
    session: str = "regular",
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    limit: int | None = Query(None, ge=1, le=5000),
) -> MarketBarsRequest:
    symbol = _resolve_symbol(ticker=ticker, option_ticker=option_ticker)
    _validate_market_symbol(
        symbol=symbol,
        is_option_ticker=bool(option_ticker and option_ticker.strip()),
    )
    normalized_timespan = normalize_timespan(timespan)
    if not is_supported_timespan(normalized_timespan):
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_TIMESPAN",
            message="timespan must be one of: minute, day, week, month",
        )
    if not is_valid_multiplier(multiplier):
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_RANGE",
            message="multiplier must be between 1 and 60",
        )
    normalized_session = session.strip().lower()
    if normalized_session not in _SUPPORTED_SESSIONS:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_SESSION",
            message="session must be one of: regular, pre, night",
        )
    if from_date is not None and to_date is not None and from_date >= to_date:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_RANGE",
            message="from must be earlier than to",
            details={"from": from_date.isoformat(), "to": to_date.isoformat()},
        )

    return MarketBarsRequest(
        symbol=symbol,
        timespan=normalized_timespan,
        multiplier=multiplier,
        session=normalized_session,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


def parse_market_snapshots_request(tickers: str) -> MarketSnapshotsRequest:
    symbols = [symbol.strip().upper() for symbol in tickers.split(",")]
    symbols = [symbol for symbol in symbols if symbol]
    if not symbols:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_TICKERS",
            message="tickers must contain at least one symbol",
        )

    unique_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        if not _TICKER_PATTERN.fullmatch(symbol):
            raise_api_error(
                status_code=400,
                code="MARKET_DATA_INVALID_TICKERS",
                message=f"invalid ticker: {symbol}",
            )
        if symbol not in seen:
            seen.add(symbol)
            unique_symbols.append(symbol)

    if len(unique_symbols) > 50:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_TOO_MANY_TICKERS",
            message="tickers cannot exceed 50 unique symbols",
        )

    return MarketSnapshotsRequest(tickers=unique_symbols)


def parse_market_trading_days_request(
    end_date: date | None = Query(None, alias="end"),
    count: int = Query(10, ge=1, le=1000),
) -> MarketTradingDaysRequest:
    return MarketTradingDaysRequest(
        end_date=end_date,
        count=count,
    )


def _resolve_symbol(*, ticker: str | None, option_ticker: str | None) -> str:
    if ticker and option_ticker:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_SYMBOL_CONFLICT",
            message="ticker and option_ticker cannot be provided together",
        )
    if not ticker and not option_ticker:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_SYMBOL_REQUIRED",
            message="ticker or option_ticker is required",
        )
    return (ticker or option_ticker or "").strip().upper()


def _validate_market_symbol(*, symbol: str, is_option_ticker: bool) -> None:
    if is_option_ticker:
        if _OPTION_TICKER_PATTERN.fullmatch(symbol):
            return
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_SYMBOL",
            message="option_ticker format is invalid",
        )

    if _TICKER_PATTERN.fullmatch(symbol):
        return
    raise_api_error(
        status_code=400,
        code="MARKET_DATA_INVALID_SYMBOL",
        message="ticker format is invalid",
    )


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


class MarketTradingDaysOut(BaseModel):
    items: list[str]
