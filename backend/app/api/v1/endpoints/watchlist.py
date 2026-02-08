from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_watchlist_service
from app.api.v1.dto.mappers import to_watchlist_item_deleted_out, to_watchlist_item_out
from app.api.v1.dto.watchlist import WatchlistItemCreate, WatchlistItemDeletedOut, WatchlistItemOut
from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.domain.auth.schemas import User

router = APIRouter()


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
    current_user: User = Depends(get_current_user),
) -> list[WatchlistItemOut]:
    items = service.list_items(user_id=current_user.id)
    return [to_watchlist_item_out(item) for item in items]


@router.post("", response_model=WatchlistItemOut)
def add_watchlist_item(
    payload: WatchlistItemCreate,
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
    current_user: User = Depends(get_current_user),
) -> WatchlistItemOut:
    try:
        item = service.add_item(user_id=current_user.id, ticker=payload.ticker)
        return to_watchlist_item_out(item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{ticker}", response_model=WatchlistItemDeletedOut)
def delete_watchlist_item(
    ticker: str,
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
    current_user: User = Depends(get_current_user),
) -> WatchlistItemDeletedOut:
    service.remove_item(user_id=current_user.id, ticker=ticker)
    return to_watchlist_item_deleted_out(ticker)
