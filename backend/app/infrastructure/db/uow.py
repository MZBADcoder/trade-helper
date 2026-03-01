from __future__ import annotations

from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.auth_repository import SqlAlchemyAuthRepository
from app.infrastructure.repositories.market_data_repository import SqlAlchemyMarketDataRepository
from app.infrastructure.repositories.watchlist_repository import SqlAlchemyWatchlistRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, *, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self.auth_repo: SqlAlchemyAuthRepository | None = None
        self.market_data_repo: SqlAlchemyMarketDataRepository | None = None
        self.watchlist_repo: SqlAlchemyWatchlistRepository | None = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.auth_repo = SqlAlchemyAuthRepository(session=self.session)
        self.market_data_repo = SqlAlchemyMarketDataRepository(session=self.session)
        self.watchlist_repo = SqlAlchemyWatchlistRepository(session=self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session is None:
            return
        if exc_type is not None:
            await self.session.rollback()
        await self.session.close()
        self.session = None
        self.auth_repo = None
        self.market_data_repo = None
        self.watchlist_repo = None

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has no active session")
        await self.session.commit()

    async def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has no active session")
        await self.session.rollback()
