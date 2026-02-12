from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.core.config import settings
from app.domain.market_data.schemas import MarketBar, MarketSnapshot
from app.infrastructure.clients.polygon import PolygonClient
from app.infrastructure.clients.polygon_mapper import map_polygon_aggregates_to_market_bars
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class DefaultMarketDataApplicationService:
    def __init__(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        polygon_client: PolygonClient | None = None,
    ) -> None:
        self._uow = uow
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

        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")
        normalized_timespan = timespan.strip().lower()
        if not normalized_timespan:
            raise ValueError("Timespan is required")
        if multiplier < 1:
            raise ValueError("Multiplier must be >= 1")
        if end_date < start_date:
            raise ValueError("End date must be on or after start date")

        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

        with self._uow as uow:
            repo = _require_market_data_repo(uow)
            coverage = repo.get_range_coverage(
                ticker=normalized,
                timespan=normalized_timespan,
                multiplier=multiplier,
            )
            if coverage and coverage[0] <= start_dt and coverage[1] >= end_dt:
                return repo.list_bars(
                    ticker=normalized,
                    timespan=normalized_timespan,
                    multiplier=multiplier,
                    start_at=start_dt,
                    end_at=end_dt,
                    limit=limit,
                )

            if self._polygon_client is None:
                raise ValueError("Polygon client not configured")

            bars = self._fetch_from_polygon(
                ticker=normalized,
                timespan=normalized_timespan,
                multiplier=multiplier,
                start_date=start_date,
                end_date=end_date,
            )
            if bars:
                repo.upsert_bars(bars)
                uow.commit()

            return repo.list_bars(
                ticker=normalized,
                timespan=normalized_timespan,
                multiplier=multiplier,
                start_at=start_dt,
                end_at=end_dt,
                limit=limit,
            )

    def prefetch_default(self, *, ticker: str) -> None:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")

        today = date.today()
        daily_start = today - timedelta(days=settings.market_data_daily_lookback_days)
        intraday_start = today - timedelta(days=settings.market_data_intraday_lookback_days)

        self.list_bars(
            ticker=normalized,
            timespan="day",
            multiplier=1,
            start_date=daily_start,
            end_date=today,
        )

    def list_snapshots(self, *, tickers: list[str]) -> list[MarketSnapshot]:
        _ = tickers
        raise ValueError("MARKET_DATA_UPSTREAM_UNAVAILABLE")
        self.list_bars(
            ticker=normalized,
            timespan="minute",
            multiplier=1,
            start_date=intraday_start,
            end_date=today,
        )

    @staticmethod
    def _default_start_date(*, timespan: str, end_date: date) -> date:
        if timespan.strip().lower() == "minute":
            return end_date - timedelta(days=settings.market_data_intraday_lookback_days)
        return end_date - timedelta(days=settings.market_data_daily_lookback_days)

    def _fetch_from_polygon(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_date: date,
        end_date: date,
    ) -> list[MarketBar]:
        aggregates = self._polygon_client.list_aggs(
            ticker=ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_date=start_date.isoformat(),
            to_date=end_date.isoformat(),
            adjusted=True,
            sort="asc",
            limit=50000,
        )
        return map_polygon_aggregates_to_market_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            aggregates=aggregates,
        )


def _require_market_data_repo(uow: SqlAlchemyUnitOfWork):
    if uow.market_data_repo is None:
        raise RuntimeError("Market data repository not configured")
    return uow.market_data_repo
