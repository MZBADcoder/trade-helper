from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert

from app.domain.market_data.schemas import MarketBar
from app.infrastructure.db.models.market_data import MarketBarModel


class SqlAlchemyMarketDataRepository:
    def __init__(self, *, session: object | None = None) -> None:
        if session is None:
            raise ValueError("session is required")
        self._session = session

    def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]:
        stmt = (
            select(MarketBarModel)
            .where(
                and_(
                    MarketBarModel.ticker == ticker,
                    MarketBarModel.timespan == timespan,
                    MarketBarModel.multiplier == multiplier,
                    MarketBarModel.start_at >= start_at,
                    MarketBarModel.start_at <= end_at,
                )
            )
            .order_by(MarketBarModel.start_at.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_schema(row) for row in rows]

    def get_range_coverage(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
    ) -> tuple[datetime, datetime] | None:
        stmt = select(func.min(MarketBarModel.start_at), func.max(MarketBarModel.start_at)).where(
            and_(
                MarketBarModel.ticker == ticker,
                MarketBarModel.timespan == timespan,
                MarketBarModel.multiplier == multiplier,
            )
        )
        result = self._session.execute(stmt).one()
        if result[0] is None or result[1] is None:
            return None
        return result[0], result[1]

    def upsert_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return
        payload = [self._to_row(bar) for bar in bars]
        stmt = insert(MarketBarModel).values(payload)
        update_cols = {
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "vwap": stmt.excluded.vwap,
            "trades": stmt.excluded.trades,
            "source": stmt.excluded.source,
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "timespan", "multiplier", "start_at"],
            set_=update_cols,
        )
        self._session.execute(stmt)
        self._session.commit()

    @staticmethod
    def _to_row(bar: MarketBar) -> dict:
        return {
            "ticker": bar.ticker,
            "timespan": bar.timespan,
            "multiplier": bar.multiplier,
            "start_at": bar.start_at,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "vwap": bar.vwap,
            "trades": bar.trades,
            "source": bar.source,
        }

    @staticmethod
    def _to_schema(item: MarketBarModel) -> MarketBar:
        return MarketBar(
            ticker=item.ticker,
            timespan=item.timespan,
            multiplier=item.multiplier,
            start_at=item.start_at,
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=item.volume,
            vwap=item.vwap,
            trades=item.trades,
            source=item.source,
        )
