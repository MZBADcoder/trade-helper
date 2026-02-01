from __future__ import annotations

from datetime import date, timedelta

from app.application.market_data.interfaces import MarketDataApplicationService
from app.core.config import settings
from app.domain.market_data.schemas import MarketBar
from app.domain.market_data.services import DefaultMarketDataService
from app.infrastructure.clients.polygon import PolygonClient
from app.repository.market_data.interfaces import MarketDataRepository


class DefaultMarketDataApplicationService(MarketDataApplicationService):
    def __init__(
        self,
        *,
        repository: MarketDataRepository | None = None,
        polygon_client: PolygonClient | None = None,
    ) -> None:
        if repository is None:
            raise ValueError("repository is required")
        self._repository = repository
        self._polygon_client = polygon_client

    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[MarketBar]:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = self._default_start_date(timespan=timespan, end_date=end_date)

        service = DefaultMarketDataService(repository=self._repository, polygon_client=self._polygon_client)
        return service.list_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def prefetch_default(self, *, ticker: str) -> None:
        service = DefaultMarketDataService(repository=self._repository, polygon_client=self._polygon_client)
        service.prefetch_default(ticker=ticker)

    @staticmethod
    def _default_start_date(*, timespan: str, end_date: date) -> date:
        if timespan.strip().lower() == "minute":
            return end_date - timedelta(days=settings.market_data_intraday_lookback_days)
        return end_date - timedelta(days=settings.market_data_daily_lookback_days)
