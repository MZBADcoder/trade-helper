from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import (
    get_current_user,
    get_market_data_service,
)
from app.api.errors import raise_api_error
from app.api.v1.dto.market_data import (
    MarketBarOut,
    MarketBarsRequest,
    MarketSnapshotsOut,
    MarketSnapshotsRequest,
    parse_market_bars_request,
    parse_market_snapshots_request,
)
from app.api.v1.dto.mappers import to_market_bar_out, to_market_snapshot_out
from app.application.market_data.errors import (
    MarketDataRangeTooLargeError,
    MarketDataRateLimitedError,
    MarketDataUpstreamUnavailableError,
)
from app.application.market_data.service import MarketDataApplicationService
from app.domain.auth.schemas import User

router = APIRouter()
_MARKET_DATA_ERROR_MAPPING = {
    MarketDataRangeTooLargeError: (
        413,
        "MARKET_DATA_RANGE_TOO_LARGE",
        "requested range is too large",
    ),
    MarketDataRateLimitedError: (
        429,
        "MARKET_DATA_RATE_LIMITED",
        "market data request rate limited",
    ),
    MarketDataUpstreamUnavailableError: (
        502,
        "MARKET_DATA_UPSTREAM_UNAVAILABLE",
        "market data upstream unavailable",
    ),
}


@router.get("/bars", response_model=list[MarketBarOut])
def list_bars(
    response: Response,
    request: MarketBarsRequest = Depends(parse_market_bars_request),
    service: MarketDataApplicationService = Depends(get_market_data_service),
    current_user: User = Depends(get_current_user),
) -> list[MarketBarOut]:
    _ = current_user
    try:
        result = service.list_bars_with_meta(
            ticker=request.symbol,
            timespan=request.timespan,
            multiplier=request.multiplier,
            start_date=request.from_date,
            end_date=request.to_date,
            limit=request.limit,
            enforce_range_limit=True,
        )
        bars = result.bars
        response.headers["X-Data-Source"] = result.data_source
        response.headers["X-Partial-Range"] = "true" if result.partial_range else "false"
        return [to_market_bar_out(bar) for bar in bars]
    except ValueError as exc:
        _raise_market_data_service_error(exc)


@router.get("/snapshots", response_model=MarketSnapshotsOut)
def list_snapshots(
    request: MarketSnapshotsRequest = Depends(parse_market_snapshots_request),
    service: MarketDataApplicationService = Depends(get_market_data_service),
    current_user: User = Depends(get_current_user),
) -> MarketSnapshotsOut:
    _ = current_user
    try:
        snapshots = service.list_snapshots(tickers=request.tickers)
        return MarketSnapshotsOut(items=[to_market_snapshot_out(snapshot) for snapshot in snapshots])
    except ValueError as exc:
        _raise_market_data_service_error(exc)


def _raise_market_data_service_error(exc: ValueError) -> None:
    for error_type, error_payload in _MARKET_DATA_ERROR_MAPPING.items():
        if isinstance(exc, error_type):
            status_code, code, message = error_payload
            raise_api_error(
                status_code=status_code,
                code=code,
                message=message,
            )
    detail = str(exc)
    raise_api_error(
        status_code=400,
        code="MARKET_DATA_INVALID_RANGE",
        message=detail,
    )
