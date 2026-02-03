from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.domain.watchlist.schemas import WatchlistItem
from app.infrastructure.db.models.watchlist import WatchlistItemModel


class SqlAlchemyWatchlistRepository:
    def __init__(self, *, session: object | None = None) -> None:
        if session is None:
            raise ValueError("session is required")
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
        return [self._to_schema(row) for row in rows]

    def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        item = WatchlistItemModel(user_id=user_id, ticker=ticker)
        self._session.add(item)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("Ticker already exists in watchlist") from exc
        self._session.refresh(item)
        return self._to_schema(item)

    def remove_item(self, *, user_id: int, ticker: str) -> None:
        self._session.execute(
            delete(WatchlistItemModel).where(
                WatchlistItemModel.user_id == user_id,
                WatchlistItemModel.ticker == ticker,
            )
        )
        self._session.commit()

    @staticmethod
    def _to_schema(item: WatchlistItemModel) -> WatchlistItem:
        created_at = item.created_at.isoformat() if item.created_at else None
        return WatchlistItem(ticker=item.ticker, created_at=created_at)
