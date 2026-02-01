from __future__ import annotations

import logging

from app.application.watchlist.interfaces import WatchlistApplicationService
from app.application.market_data.interfaces import MarketDataApplicationService
from app.domain.watchlist.interfaces import WatchlistService
from app.domain.watchlist.services import DefaultWatchlistService
from app.domain.watchlist.schemas import WatchlistItem
from app.repository.watchlist.interfaces import WatchlistRepository

logger = logging.getLogger(__name__)


class DefaultWatchlistApplicationService(WatchlistApplicationService):
    def __init__(
        self,
        *,
        service: WatchlistService | None = None,
        repository: WatchlistRepository | None = None,
        market_data_service: MarketDataApplicationService | None = None,
    ) -> None:
        self._service = service
        self._repository = repository
        self._market_data_service = market_data_service

    def list_items(self) -> list[WatchlistItem]:
        return self._resolve_service().list_items()

    def add_item(self, *, ticker: str) -> WatchlistItem:
        item = self._resolve_service().add_item(ticker=ticker)

        if self._market_data_service is not None:
            try:
                self._market_data_service.prefetch_default(ticker=item.ticker)
            except Exception:
                logger.exception("Market data prefetch failed", extra={"ticker": item.ticker})

        return item

    def remove_item(self, *, ticker: str) -> None:
        self._resolve_service().remove_item(ticker=ticker)
        return None

    def _resolve_service(self) -> WatchlistService:
        if self._service is not None:
            return self._service
        if self._repository is None:
            raise ValueError("repository is required")
        return DefaultWatchlistService(repository=self._repository)
