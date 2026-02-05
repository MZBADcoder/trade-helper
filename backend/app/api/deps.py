from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application import container
from app.application.auth.service import DefaultAuthApplicationService
from app.application.market_data.service import DefaultMarketDataApplicationService
from app.application.watchlist.service import DefaultWatchlistApplicationService
from app.domain.auth.schemas import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_market_data_service() -> DefaultMarketDataApplicationService:
    return container.build_market_data_service()


def get_watchlist_service() -> DefaultWatchlistApplicationService:
    return container.build_watchlist_service()


def get_auth_service() -> DefaultAuthApplicationService:
    return container.build_auth_service()


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
