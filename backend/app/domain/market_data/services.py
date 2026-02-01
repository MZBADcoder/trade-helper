from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.core.config import settings
from app.infrastructure.clients.polygon import PolygonClient
from app.domain.market_data.schemas import MarketBar
from app.repository.market_data.interfaces import MarketDataRepository
from app.domain.market_data.interfaces import MarketDataService


class DefaultMarketDataService(MarketDataService):
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
        multiplier: int,
        start_date: date,
        end_date: date,
        limit: int | None = None,
    ) -> list[MarketBar]:
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

        coverage = self._repository.get_range_coverage(
            ticker=normalized,
            timespan=normalized_timespan,
            multiplier=multiplier,
        )
        if coverage and coverage[0] <= start_dt and coverage[1] >= end_dt:
            return self._repository.list_bars(
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
            self._repository.upsert_bars(bars)

        return self._repository.list_bars(
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
        self.list_bars(
            ticker=normalized,
            timespan="minute",
            multiplier=1,
            start_date=intraday_start,
            end_date=today,
        )

    def _fetch_from_polygon(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_date: date,
        end_date: date,
    ) -> list[MarketBar]:
        path = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start_date.isoformat()}/{end_date.isoformat()}"
        payload = self._polygon_client.get(
            path,
            params={
                "adjusted": "true",
                "sort": "asc",
                "limit": 50000,
            },
        )

        results = payload.get("results") or []
        bars: list[MarketBar] = []
        for item in results:
            timestamp_ms = item.get("t")
            if timestamp_ms is None:
                continue
            start_at = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            bars.append(
                MarketBar(
                    ticker=ticker,
                    timespan=timespan,
                    multiplier=multiplier,
                    start_at=start_at,
                    open=float(item.get("o", 0.0)),
                    high=float(item.get("h", 0.0)),
                    low=float(item.get("l", 0.0)),
                    close=float(item.get("c", 0.0)),
                    volume=float(item.get("v", 0.0)),
                    vwap=float(item["vw"]) if item.get("vw") is not None else None,
                    trades=int(item["n"]) if item.get("n") is not None else None,
                )
            )

        return bars
