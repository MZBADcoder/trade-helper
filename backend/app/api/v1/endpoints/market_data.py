from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_current_user, get_market_data_service
from app.api.errors import raise_api_error
from app.api.v1.dto.market_data import MarketBarOut, MarketSnapshotsOut
from app.api.v1.dto.mappers import to_market_bar_out, to_market_snapshot_out
from app.application.market_data.service import DefaultMarketDataApplicationService
from app.domain.auth.schemas import User

router = APIRouter()
_TIMESPANS = {"minute", "day", "week", "month"}
_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")


@router.get("/bars", response_model=list[MarketBarOut])
def list_bars(
    response: Response,
    ticker: str | None = None,
    option_ticker: str | None = None,
    timespan: str = "day",
    multiplier: int = 1,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    limit: int | None = Query(None, ge=1, le=5000),
    service: DefaultMarketDataApplicationService = Depends(get_market_data_service),
    current_user: User = Depends(get_current_user),
) -> list[MarketBarOut]:
    _ = current_user

    symbol = _resolve_symbol(ticker=ticker, option_ticker=option_ticker)
    normalized_timespan = timespan.strip().lower()
    if normalized_timespan not in _TIMESPANS:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_TIMESPAN",
            message="timespan must be one of: minute, day, week, month",
        )
    if multiplier < 1 or multiplier > 60:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_RANGE",
            message="multiplier must be between 1 and 60",
        )
    if from_date is not None and to_date is not None and from_date >= to_date:
        raise_api_error(
            status_code=400,
            code="MARKET_DATA_INVALID_RANGE",
            message="from must be earlier than to",
            details={"from": from_date.isoformat(), "to": to_date.isoformat()},
        )
    if _is_range_too_large(
        timespan=normalized_timespan,
        multiplier=multiplier,
        from_date=from_date,
        to_date=to_date,
    ):
        raise_api_error(
            status_code=413,
            code="MARKET_DATA_RANGE_TOO_LARGE",
            message="requested range is too large",
        )
    try:
        bars = service.list_bars(
            ticker=symbol,
            timespan=normalized_timespan,
            multiplier=multiplier,
            start_date=from_date,
            end_date=to_date,
            limit=limit,
        )
        response.headers["X-Data-Source"] = "REST"
        response.headers["X-Partial-Range"] = "false"
        return [to_market_bar_out(bar) for bar in bars]
    except ValueError as exc:
        _raise_market_data_service_error(exc)


@router.get("/snapshots", response_model=MarketSnapshotsOut)
def list_snapshots(
    tickers: str,
    service: DefaultMarketDataApplicationService = Depends(get_market_data_service),
    current_user: User = Depends(get_current_user),
) -> MarketSnapshotsOut:
    _ = current_user
    parsed = _parse_tickers(tickers)
    try:
        snapshots = service.list_snapshots(tickers=parsed)
        return MarketSnapshotsOut(items=[to_market_snapshot_out(snapshot) for snapshot in snapshots])
    except ValueError as exc:
        _raise_market_data_service_error(exc)


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


def _parse_tickers(raw: str) -> list[str]:
    symbols = [symbol.strip().upper() for symbol in raw.split(",")]
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
    return unique_symbols


def _is_range_too_large(
    *,
    timespan: str,
    multiplier: int,
    from_date: date | None,
    to_date: date | None,
) -> bool:
    if from_date is None or to_date is None:
        return False
    days = (to_date - from_date).days
    if days <= 0:
        return False

    if timespan == "minute":
        estimated_points = (days * 24 * 60) // multiplier
    elif timespan == "day":
        estimated_points = days // multiplier
    elif timespan == "week":
        estimated_points = days // (7 * multiplier)
    else:
        estimated_points = days // (30 * multiplier)
    return estimated_points > 5000


def _raise_market_data_service_error(exc: ValueError) -> None:
    detail = str(exc)
    if detail == "MARKET_DATA_RATE_LIMITED":
        raise_api_error(
            status_code=429,
            code="MARKET_DATA_RATE_LIMITED",
            message="market data request rate limited",
        )
    if detail in {
        "MARKET_DATA_UPSTREAM_UNAVAILABLE",
        "Massive client not configured",
    }:
        raise_api_error(
            status_code=502,
            code="MARKET_DATA_UPSTREAM_UNAVAILABLE",
            message="market data upstream unavailable",
        )
    raise_api_error(
        status_code=400,
        code="MARKET_DATA_INVALID_RANGE",
        message=detail,
    )
