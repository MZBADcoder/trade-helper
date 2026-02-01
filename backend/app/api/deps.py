from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.market_data.service import DefaultMarketDataApplicationService
from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.core.config import settings
from app.infrastructure.clients.polygon import PolygonClient
from app.infrastructure.db.session import get_db
from app.repository.market_data.repo import SqlAlchemyMarketDataRepository
from app.repository.watchlist.repo import SqlAlchemyWatchlistRepository


def _get_polygon_client() -> PolygonClient | None:
    if not settings.polygon_api_key:
        return None
    return PolygonClient(settings.polygon_api_key)


def get_market_data_service(db: Session = Depends(get_db)) -> DefaultMarketDataApplicationService:
    repository = SqlAlchemyMarketDataRepository(session=db)
    polygon_client = _get_polygon_client()
    return DefaultMarketDataApplicationService(repository=repository, polygon_client=polygon_client)


def get_watchlist_service(db: Session = Depends(get_db)) -> DefaultWatchlistApplicationService:
    watchlist_repo = SqlAlchemyWatchlistRepository(session=db)
    market_data_repo = SqlAlchemyMarketDataRepository(session=db)
    polygon_client = _get_polygon_client()
    market_data_service = DefaultMarketDataApplicationService(
        repository=market_data_repo,
        polygon_client=polygon_client,
    )
    return DefaultWatchlistApplicationService(
        repository=watchlist_repo,
        market_data_service=market_data_service,
    )
