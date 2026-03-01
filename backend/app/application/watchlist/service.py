from __future__ import annotations

import logging
import re

from app.application.market_data.service import MarketDataApplicationService
from app.domain.watchlist.schemas import WatchlistItem
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)
_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")


class WatchlistApplicationService:
    def __init__(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        market_data_service: MarketDataApplicationService | None = None,
    ) -> None:
        self._uow = uow
        self._market_data_service = market_data_service

    async def list_items(self, *, user_id: int) -> list[WatchlistItem]:
        _validate_user_id(user_id=user_id)
        async with self._uow as uow:
            repo = _require_watchlist_repo(uow)
            return await repo.list_items(user_id=user_id)

    async def add_item(self, *, user_id: int, ticker: str) -> WatchlistItem:
        _validate_user_id(user_id=user_id)
        normalized = _normalize_ticker(ticker)
        async with self._uow as uow:
            repo = _require_watchlist_repo(uow)
            item = await repo.add_item(user_id=user_id, ticker=normalized)
            await uow.commit()

        if self._market_data_service is not None:
            try:
                await self._market_data_service.prefetch_default(ticker=item.ticker)
            except Exception:
                logger.exception("Market data prefetch failed", extra={"ticker": item.ticker})

        return item

    async def remove_item(self, *, user_id: int, ticker: str) -> None:
        _validate_user_id(user_id=user_id)
        normalized = _normalize_ticker(ticker)
        async with self._uow as uow:
            repo = _require_watchlist_repo(uow)
            await repo.remove_item(user_id=user_id, ticker=normalized)
            await uow.commit()
        return None


def _require_watchlist_repo(uow: SqlAlchemyUnitOfWork):
    if uow.watchlist_repo is None:
        raise RuntimeError("Watchlist repository not configured")
    return uow.watchlist_repo


def _normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("Ticker is required")
    if not _TICKER_PATTERN.fullmatch(normalized):
        raise ValueError("Ticker format is invalid")
    return normalized


def _validate_user_id(*, user_id: int) -> None:
    if user_id < 1:
        raise ValueError("Invalid user id")
