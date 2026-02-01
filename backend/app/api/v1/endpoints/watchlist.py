from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.api.v1.dto.watchlist import WatchlistItemCreate, WatchlistItemOut
from app.application.market_data.service import DefaultMarketDataApplicationService
from app.core.config import settings
from app.infrastructure.clients.polygon import PolygonClient
from app.infrastructure.db.session import get_db
from app.repository.market_data.repo import SqlAlchemyMarketDataRepository
from app.repository.watchlist.repo import SqlAlchemyWatchlistRepository

router = APIRouter()


def _build_service(db: Session) -> DefaultWatchlistApplicationService:
    watchlist_repo = SqlAlchemyWatchlistRepository(session=db)
    market_data_repo = SqlAlchemyMarketDataRepository(session=db)
    polygon_client = PolygonClient(settings.polygon_api_key) if settings.polygon_api_key else None
    market_data_service = DefaultMarketDataApplicationService(
        repository=market_data_repo,
        polygon_client=polygon_client,
    )
    return DefaultWatchlistApplicationService(
        repository=watchlist_repo,
        market_data_service=market_data_service,
    )


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(db: Session = Depends(get_db)) -> list[WatchlistItemOut]:
    service = _build_service(db)
    items = service.list_items()
    return [WatchlistItemOut(**item.model_dump()) for item in items]


@router.post("", response_model=WatchlistItemOut)
def add_watchlist_item(payload: WatchlistItemCreate, db: Session = Depends(get_db)) -> WatchlistItemOut:
    service = _build_service(db)
    try:
        item = service.add_item(ticker=payload.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WatchlistItemOut(**item.model_dump())


@router.delete("/{ticker}")
def delete_watchlist_item(ticker: str, db: Session = Depends(get_db)) -> dict:
    service = _build_service(db)
    service.remove_item(ticker=ticker)
    return {"deleted": ticker.upper()}
