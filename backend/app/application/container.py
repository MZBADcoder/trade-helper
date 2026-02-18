from __future__ import annotations

from functools import lru_cache

from app.application.auth.service import AuthApplicationService
from app.application.market_data.service import MarketDataApplicationService
from app.application.options.service import OptionsApplicationService
from app.application.watchlist.service import WatchlistApplicationService
from app.core.config import settings
from app.infrastructure.clients.massive import MassiveClient
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@lru_cache
def _massive_client() -> MassiveClient | None:
    if not settings.massive_api_key:
        return None
    return MassiveClient(settings.massive_api_key)


def build_uow() -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory=SessionLocal)


def build_market_data_service() -> MarketDataApplicationService:
    return MarketDataApplicationService(
        uow=build_uow(),
        massive_client=_massive_client(),
    )


def build_watchlist_service() -> WatchlistApplicationService:
    return WatchlistApplicationService(
        uow=build_uow(),
        market_data_service=build_market_data_service(),
    )


def build_options_service() -> OptionsApplicationService:
    return OptionsApplicationService(
        massive_client=_massive_client(),
        enabled=settings.options_data_enabled,
    )


def build_auth_service() -> AuthApplicationService:
    return AuthApplicationService(uow=build_uow())
