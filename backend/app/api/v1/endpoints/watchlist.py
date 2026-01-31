from fastapi import APIRouter, HTTPException

from app.db.session import db
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemOut

router = APIRouter()


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist() -> list[WatchlistItemOut]:
    items = db.watchlist_list()
    return [WatchlistItemOut(**item) for item in items]


@router.post("", response_model=WatchlistItemOut)
def add_watchlist_item(payload: WatchlistItemCreate) -> WatchlistItemOut:
    try:
        item = db.watchlist_add(ticker=payload.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WatchlistItemOut(**item)


@router.delete("/{ticker}")
def delete_watchlist_item(ticker: str) -> dict:
    db.watchlist_remove(ticker=ticker)
    return {"deleted": ticker.upper()}

