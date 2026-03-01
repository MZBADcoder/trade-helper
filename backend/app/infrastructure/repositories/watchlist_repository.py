from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.watchlist.schemas import WatchlistItem
from app.infrastructure.db.mappers import watchlist_item_to_domain
from app.infrastructure.db.models.watchlist import WatchlistItemModel


class SqlAlchemyWatchlistRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        rows = (
            (
                await self._session.execute(
                    select(WatchlistItemModel)
                    .where(WatchlistItemModel.user_id == user_id)
                    .order_by(WatchlistItemModel.ticker)
                )
            )
            .scalars()
            .all()
        )
        return [watchlist_item_to_domain(row) for row in rows]

    async def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        item = WatchlistItemModel(user_id=user_id, ticker=ticker)
        self._session.add(item)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ValueError("Ticker already exists in watchlist") from exc
        return watchlist_item_to_domain(item)

    async def remove_item(self, *, user_id: int, ticker: str) -> None:
        await self._session.execute(
            delete(WatchlistItemModel).where(
                WatchlistItemModel.user_id == user_id,
                WatchlistItemModel.ticker == ticker,
            )
        )
        await self._session.flush()
