from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.watchlist.schemas import WatchlistItem
from app.infrastructure.db.mappers import watchlist_item_to_domain
from app.infrastructure.db.models.watchlist import WatchlistItemModel


class SqlAlchemyWatchlistRepository:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        rows = (
            self._session.execute(
                select(WatchlistItemModel)
                .where(WatchlistItemModel.user_id == user_id)
                .order_by(WatchlistItemModel.ticker)
            )
            .scalars()
            .all()
        )
        return [watchlist_item_to_domain(row) for row in rows]

    def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        item = WatchlistItemModel(user_id=user_id, ticker=ticker)
        self._session.add(item)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("Ticker already exists in watchlist") from exc
        return watchlist_item_to_domain(item)

    def remove_item(self, *, user_id: int, ticker: str) -> None:
        self._session.execute(
            delete(WatchlistItemModel).where(
                WatchlistItemModel.user_id == user_id,
                WatchlistItemModel.ticker == ticker,
            )
        )
        self._session.flush()
