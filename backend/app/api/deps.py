from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.auth.service import DefaultAuthApplicationService
from app.application.market_data.service import DefaultMarketDataApplicationService
from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.core.config import settings
from app.domain.auth.schemas import User
from app.infrastructure.clients.polygon import PolygonClient
from app.infrastructure.db.session import get_db
from app.repository.auth.repo import SqlAlchemyAuthRepository
from app.repository.market_data.repo import SqlAlchemyMarketDataRepository
from app.repository.watchlist.repo import SqlAlchemyWatchlistRepository

bearer_scheme = HTTPBearer(auto_error=False)


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


def get_auth_service(db: Session = Depends(get_db)) -> DefaultAuthApplicationService:
    repository = SqlAlchemyAuthRepository(session=db)
    return DefaultAuthApplicationService(repository=repository)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: DefaultAuthApplicationService = Depends(get_auth_service),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized_error()

    try:
        return service.get_current_user_from_token(token=credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _unauthorized_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided",
        headers={"WWW-Authenticate": "Bearer"},
    )
