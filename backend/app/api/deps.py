from __future__ import annotations

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.errors import raise_api_error
from app.application import container
from app.application.auth.service import AuthApplicationService
from app.application.market_data.service import MarketDataApplicationService
from app.application.options.service import OptionsApplicationService
from app.application.watchlist.service import WatchlistApplicationService
from app.domain.auth.schemas import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_market_data_service() -> MarketDataApplicationService:
    return container.build_market_data_service()


def get_watchlist_service() -> WatchlistApplicationService:
    return container.build_watchlist_service()


def get_options_service() -> OptionsApplicationService:
    return container.build_options_service()


def get_auth_service() -> AuthApplicationService:
    return container.build_auth_service()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: AuthApplicationService = Depends(get_auth_service),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized_error()

    try:
        return service.get_current_user_from_token(token=credentials.credentials)
    except ValueError as exc:
        raise_api_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_UNAUTHORIZED",
            message=str(exc),
        )


def _unauthorized_error() -> None:
    raise_api_error(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="AUTH_UNAUTHORIZED",
        message="Authentication credentials were not provided",
    )
