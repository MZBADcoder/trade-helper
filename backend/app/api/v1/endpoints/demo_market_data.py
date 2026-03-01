from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_demo_market_data_service
from app.api.errors import raise_api_error
from app.api.v1.dto.market_data import (
    MarketBarOut,
    MarketBarsRequest,
    MarketSnapshotsOut,
    MarketSnapshotsRequest,
    parse_market_bars_request,
    parse_market_snapshots_request,
)
from app.api.v1.dto.mappers import to_market_bar_out, to_market_snapshot_out, to_watchlist_item_out
from app.api.v1.dto.watchlist import WatchlistItemOut
from app.application.demo_market.service import DemoMarketDataApplicationService

router = APIRouter()


@router.get("/watchlist", response_model=list[WatchlistItemOut])
async def list_demo_watchlist(
    service: DemoMarketDataApplicationService = Depends(get_demo_market_data_service),
) -> list[WatchlistItemOut]:
    items = await service.list_watchlist()
    return [to_watchlist_item_out(item) for item in items]


@router.get("/market-data/bars", response_model=list[MarketBarOut])
async def list_demo_bars(
    response: Response,
    request: MarketBarsRequest = Depends(parse_market_bars_request),
    service: DemoMarketDataApplicationService = Depends(get_demo_market_data_service),
) -> list[MarketBarOut]:
    try:
        result = await service.list_bars_with_meta(
            ticker=request.symbol,
            timespan=request.timespan,
            multiplier=request.multiplier,
            start_date=request.from_date,
            end_date=request.to_date,
            limit=request.limit,
        )
    except ValueError as exc:
        _raise_demo_market_data_error(exc)
    response.headers["X-Data-Source"] = result.data_source
    response.headers["X-Partial-Range"] = "true" if result.partial_range else "false"
    return [to_market_bar_out(item) for item in result.bars]


@router.get("/market-data/snapshots", response_model=MarketSnapshotsOut)
async def list_demo_snapshots(
    request: MarketSnapshotsRequest = Depends(parse_market_snapshots_request),
    service: DemoMarketDataApplicationService = Depends(get_demo_market_data_service),
) -> MarketSnapshotsOut:
    try:
        snapshots = await service.list_snapshots(tickers=request.tickers)
    except ValueError as exc:
        _raise_demo_market_data_error(exc)
    return MarketSnapshotsOut(items=[to_market_snapshot_out(snapshot) for snapshot in snapshots])


def _raise_demo_market_data_error(exc: ValueError) -> None:
    raise_api_error(
        status_code=400,
        code="DEMO_MARKET_DATA_INVALID_REQUEST",
        message=str(exc),
    )
