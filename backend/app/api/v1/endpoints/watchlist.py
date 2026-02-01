from fastapi import APIRouter, HTTPException

from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.api.dto.watchlist import WatchlistItemCreate, WatchlistItemOut

router = APIRouter()


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist() -> list[WatchlistItemOut]:
    service = DefaultWatchlistApplicationService()
    items = service.list_items()
    return [WatchlistItemOut(**item) for item in items]


@router.post("", response_model=WatchlistItemOut)
def add_watchlist_item(payload: WatchlistItemCreate) -> WatchlistItemOut:
    service = DefaultWatchlistApplicationService()
    try:
        item = service.add_item(ticker=payload.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WatchlistItemOut(**item)


@router.delete("/{ticker}")
def delete_watchlist_item(ticker: str) -> dict:
    service = DefaultWatchlistApplicationService()
    service.remove_item(ticker=ticker)
    return {"deleted": ticker.upper()}
