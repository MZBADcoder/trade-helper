from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_watchlist_service
from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.api.v1.dto.watchlist import WatchlistItemCreate, WatchlistItemOut

router = APIRouter()


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
) -> list[WatchlistItemOut]:
    items = service.list_items()
    return [WatchlistItemOut(**item.model_dump()) for item in items]


@router.post("", response_model=WatchlistItemOut)
def add_watchlist_item(
    payload: WatchlistItemCreate,
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
) -> WatchlistItemOut:
    try:
        item = service.add_item(ticker=payload.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WatchlistItemOut(**item.model_dump())


@router.delete("/{ticker}")
def delete_watchlist_item(
    ticker: str,
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
) -> dict:
    service.remove_item(ticker=ticker)
    return {"deleted": ticker.upper()}
