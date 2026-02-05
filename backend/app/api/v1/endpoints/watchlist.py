from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_watchlist_service
from app.api.v1.dto.watchlist import WatchlistItemCreate, WatchlistItemOut
from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.domain.auth.schemas import User

router = APIRouter()


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
    current_user: User = Depends(get_current_user),
) -> list[WatchlistItemOut]:
    return service.list_items(user_id=current_user.id)


@router.post("", response_model=WatchlistItemOut)
def add_watchlist_item(
    payload: WatchlistItemCreate,
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
    current_user: User = Depends(get_current_user),
) -> WatchlistItemOut:
    try:
        return service.add_item(user_id=current_user.id, ticker=payload.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{ticker}")
def delete_watchlist_item(
    ticker: str,
    service: DefaultWatchlistApplicationService = Depends(get_watchlist_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    service.remove_item(user_id=current_user.id, ticker=ticker)
    return {"deleted": ticker.upper()}
