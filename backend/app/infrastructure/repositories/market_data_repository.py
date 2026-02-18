from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.market_data.schemas import MarketBar
from app.infrastructure.db.mappers import (
    market_bar_day_to_domain,
    market_bar_minute_agg_to_domain,
    market_bar_minute_to_domain,
    market_bar_to_day_row,
    market_bar_to_minute_agg_row,
    market_bar_to_minute_row,
)
from app.infrastructure.db.models.market_data import (
    MarketBarDayModel,
    MarketBarMinuteAggModel,
    MarketBarMinuteModel,
)

_MARKET_TZ = ZoneInfo("America/New_York")


class SqlAlchemyMarketDataRepository:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def list_day_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]:
        stmt = (
            select(MarketBarDayModel)
            .where(
                and_(
                    MarketBarDayModel.ticker == ticker,
                    MarketBarDayModel.start_at >= start_at,
                    MarketBarDayModel.start_at <= end_at,
                )
            )
            .order_by(MarketBarDayModel.start_at.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [market_bar_day_to_domain(row) for row in rows]

    def list_minute_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
    ) -> list[MarketBar]:
        stmt = (
            select(MarketBarMinuteModel)
            .where(
                and_(
                    MarketBarMinuteModel.ticker == ticker,
                    MarketBarMinuteModel.start_at >= start_at,
                    MarketBarMinuteModel.start_at <= end_at,
                )
            )
            .order_by(MarketBarMinuteModel.start_at.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [market_bar_minute_to_domain(row) for row in rows]

    def list_minute_agg_bars(
        self,
        *,
        ticker: str,
        multiplier: int,
        start_at: datetime,
        end_at: datetime,
        final_only: bool = True,
        limit: int | None = None,
    ) -> list[MarketBar]:
        conditions = [
            MarketBarMinuteAggModel.ticker == ticker,
            MarketBarMinuteAggModel.multiplier == multiplier,
            MarketBarMinuteAggModel.bucket_start_at >= start_at,
            MarketBarMinuteAggModel.bucket_start_at <= end_at,
        ]
        if final_only:
            conditions.append(MarketBarMinuteAggModel.is_final.is_(True))
        stmt = select(MarketBarMinuteAggModel).where(and_(*conditions)).order_by(
            MarketBarMinuteAggModel.bucket_start_at.asc()
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [market_bar_minute_agg_to_domain(row) for row in rows]

    def list_minute_bars_for_bucket(
        self,
        *,
        ticker: str,
        bucket_start_at: datetime,
        bucket_end_at: datetime,
    ) -> list[MarketBar]:
        stmt = (
            select(MarketBarMinuteModel)
            .where(
                and_(
                    MarketBarMinuteModel.ticker == ticker,
                    MarketBarMinuteModel.start_at >= bucket_start_at,
                    MarketBarMinuteModel.start_at < bucket_end_at,
                )
            )
            .order_by(MarketBarMinuteModel.start_at.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [market_bar_minute_to_domain(row) for row in rows]

    def get_day_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        stmt = select(func.min(MarketBarDayModel.start_at), func.max(MarketBarDayModel.start_at)).where(
            MarketBarDayModel.ticker == ticker
        )
        result = self._session.execute(stmt).one()
        if result[0] is None or result[1] is None:
            return None
        return result[0], result[1]

    def get_minute_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        stmt = select(func.min(MarketBarMinuteModel.start_at), func.max(MarketBarMinuteModel.start_at)).where(
            MarketBarMinuteModel.ticker == ticker
        )
        result = self._session.execute(stmt).one()
        if result[0] is None or result[1] is None:
            return None
        return result[0], result[1]

    def get_minute_agg_range_coverage(
        self,
        *,
        ticker: str,
        multiplier: int,
    ) -> tuple[datetime, datetime] | None:
        stmt = select(
            func.min(MarketBarMinuteAggModel.bucket_start_at),
            func.max(MarketBarMinuteAggModel.bucket_start_at),
        ).where(
            and_(
                MarketBarMinuteAggModel.ticker == ticker,
                MarketBarMinuteAggModel.multiplier == multiplier,
                MarketBarMinuteAggModel.is_final.is_(True),
            )
        )
        result = self._session.execute(stmt).one()
        if result[0] is None or result[1] is None:
            return None
        return result[0], result[1]

    def list_minute_tickers(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[str]:
        stmt = (
            select(MarketBarMinuteModel.ticker)
            .where(
                and_(
                    MarketBarMinuteModel.start_at >= start_at,
                    MarketBarMinuteModel.start_at <= end_at,
                )
            )
            .distinct()
            .order_by(MarketBarMinuteModel.ticker.asc())
        )
        rows = self._session.execute(stmt).all()
        return [row[0] for row in rows if row and row[0]]

    def upsert_day_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        payload = [
            market_bar_to_day_row(
                bar,
                trade_date=_to_market_trade_date(bar.start_at),
            )
            for bar in bars
        ]
        stmt = insert(MarketBarDayModel).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "trade_date"],
            set_=_update_columns(
                stmt,
                [
                    "start_at",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "vwap",
                    "trades",
                    "source",
                ],
            ),
        )
        self._session.execute(stmt)

    def upsert_minute_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        payload = [
            market_bar_to_minute_row(
                bar,
                trade_date=_to_market_trade_date(bar.start_at),
            )
            for bar in bars
        ]
        stmt = insert(MarketBarMinuteModel).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "start_at"],
            set_=_update_columns(
                stmt,
                [
                    "trade_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "vwap",
                    "trades",
                    "source",
                ],
            ),
        )
        self._session.execute(stmt)

    def upsert_minute_agg_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        payload = [
            market_bar_to_minute_agg_row(
                bar,
                trade_date=_to_market_trade_date(bar.start_at),
            )
            for bar in bars
        ]
        stmt = insert(MarketBarMinuteAggModel).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "multiplier", "bucket_start_at"],
            set_=_update_columns(
                stmt,
                [
                    "trade_date",
                    "bucket_end_at",
                    "is_final",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "vwap",
                    "trades",
                    "source",
                ],
            ),
        )
        self._session.execute(stmt)

    def delete_minute_bars_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        stmt = delete(MarketBarMinuteModel).where(MarketBarMinuteModel.trade_date < keep_from_trade_date)
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)

    def delete_minute_agg_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        stmt = delete(MarketBarMinuteAggModel).where(MarketBarMinuteAggModel.trade_date < keep_from_trade_date)
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)

    # Compatibility wrappers for existing callers/tests.
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
        if timespan == "day" and multiplier == 1:
            return self.list_day_bars(ticker=ticker, start_at=start_at, end_at=end_at, limit=limit)
        if timespan == "minute" and multiplier == 1:
            return self.list_minute_bars(ticker=ticker, start_at=start_at, end_at=end_at, limit=limit)
        if timespan == "minute" and multiplier > 1:
            return self.list_minute_agg_bars(
                ticker=ticker,
                multiplier=multiplier,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
            )
        return []

    def get_range_coverage(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
    ) -> tuple[datetime, datetime] | None:
        if timespan == "day" and multiplier == 1:
            return self.get_day_range_coverage(ticker=ticker)
        if timespan == "minute" and multiplier == 1:
            return self.get_minute_range_coverage(ticker=ticker)
        if timespan == "minute" and multiplier > 1:
            return self.get_minute_agg_range_coverage(ticker=ticker, multiplier=multiplier)
        return None

    def upsert_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        first = bars[0]
        if first.timespan == "day" and first.multiplier == 1:
            self.upsert_day_bars(bars)
            return
        if first.timespan == "minute" and first.multiplier == 1:
            self.upsert_minute_bars(bars)
            return
        if first.timespan == "minute" and first.multiplier > 1:
            self.upsert_minute_agg_bars(bars)
            return


def _update_columns(stmt, columns: list[str]) -> dict[str, object]:
    return {column: getattr(stmt.excluded, column) for column in columns}


def _to_market_trade_date(start_at: datetime) -> date:
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)
    return start_at.astimezone(_MARKET_TZ).date()
