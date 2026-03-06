from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Time, and_, cast, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

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
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def list_day_bars(
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
        rows = (await self._session.execute(stmt)).scalars().all()
        return [market_bar_day_to_domain(row) for row in rows]

    async def list_recent_day_bars(
        self,
        *,
        ticker: str,
        limit: int = 2,
    ) -> list[MarketBar]:
        if limit < 1:
            return []

        stmt = (
            select(MarketBarDayModel)
            .where(MarketBarDayModel.ticker == ticker)
            .order_by(MarketBarDayModel.trade_date.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        bars = [market_bar_day_to_domain(row) for row in rows]
        bars.sort(key=lambda bar: bar.start_at)
        return bars

    async def list_minute_bars(
        self,
        *,
        ticker: str,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
        session: str | None = None,
    ) -> list[MarketBar]:
        conditions = [
            MarketBarMinuteModel.ticker == ticker,
            MarketBarMinuteModel.start_at >= start_at,
            MarketBarMinuteModel.start_at <= end_at,
        ]
        if session:
            conditions.extend(_minute_session_conditions(session=session))

        stmt = select(MarketBarMinuteModel).where(and_(*conditions)).order_by(MarketBarMinuteModel.start_at.asc())
        if limit:
            stmt = stmt.limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [market_bar_minute_to_domain(row) for row in rows]

    async def list_minute_agg_bars(
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
        rows = (await self._session.execute(stmt)).scalars().all()
        return [market_bar_minute_agg_to_domain(row) for row in rows]

    async def list_minute_bars_for_bucket(
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
        rows = (await self._session.execute(stmt)).scalars().all()
        return [market_bar_minute_to_domain(row) for row in rows]

    async def get_day_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        stmt = select(func.min(MarketBarDayModel.start_at), func.max(MarketBarDayModel.start_at)).where(
            MarketBarDayModel.ticker == ticker
        )
        result = (await self._session.execute(stmt)).one()
        if result[0] is None or result[1] is None:
            return None
        return result[0], result[1]

    async def get_minute_range_coverage(self, *, ticker: str) -> tuple[datetime, datetime] | None:
        stmt = select(func.min(MarketBarMinuteModel.start_at), func.max(MarketBarMinuteModel.start_at)).where(
            MarketBarMinuteModel.ticker == ticker
        )
        result = (await self._session.execute(stmt)).one()
        if result[0] is None or result[1] is None:
            return None
        return result[0], result[1]

    async def get_minute_agg_range_coverage(
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
        result = (await self._session.execute(stmt)).one()
        if result[0] is None or result[1] is None:
            return None
        return result[0], result[1]

    async def list_minute_tickers(
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
        rows = (await self._session.execute(stmt)).all()
        return [row[0] for row in rows if row and row[0]]

    async def list_recent_minute_trade_dates(self, *, limit: int) -> list[date]:
        if limit < 1:
            return []
        stmt = (
            select(MarketBarMinuteModel.trade_date)
            .distinct()
            .order_by(MarketBarMinuteModel.trade_date.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [row[0] for row in rows if row and row[0] is not None]

    async def list_recent_minute_agg_trade_dates(self, *, limit: int) -> list[date]:
        if limit < 1:
            return []
        stmt = (
            select(MarketBarMinuteAggModel.trade_date)
            .distinct()
            .order_by(MarketBarMinuteAggModel.trade_date.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [row[0] for row in rows if row and row[0] is not None]

    async def upsert_day_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        payload = [
            market_bar_to_day_row(
                bar,
                trade_date=_to_market_trade_date(bar.start_at),
            )
            for bar in bars
        ]
        for chunk in _chunk_insert_payload(payload):
            stmt = insert(MarketBarDayModel).values(chunk)
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
                        "is_final",
                        "source",
                    ],
                    monotonic_true_columns={"is_final"},
                ),
            )
            await self._session.execute(stmt)

    async def upsert_minute_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        payload = [
            market_bar_to_minute_row(
                bar,
                trade_date=_to_market_trade_date(bar.start_at),
            )
            for bar in bars
        ]
        for chunk in _chunk_insert_payload(payload):
            stmt = insert(MarketBarMinuteModel).values(chunk)
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
                        "is_final",
                        "source",
                    ],
                    monotonic_true_columns={"is_final"},
                ),
            )
            await self._session.execute(stmt)

    async def upsert_minute_agg_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        payload = [
            market_bar_to_minute_agg_row(
                bar,
                trade_date=_to_market_trade_date(bar.start_at),
            )
            for bar in bars
        ]
        for chunk in _chunk_insert_payload(payload):
            stmt = insert(MarketBarMinuteAggModel).values(chunk)
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
            await self._session.execute(stmt)

    async def delete_minute_bars_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        stmt = delete(MarketBarMinuteModel).where(MarketBarMinuteModel.trade_date < keep_from_trade_date)
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)

    async def delete_minute_agg_before_trade_date(self, *, keep_from_trade_date: date) -> int:
        stmt = delete(MarketBarMinuteAggModel).where(MarketBarMinuteAggModel.trade_date < keep_from_trade_date)
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)

    async def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_at: datetime,
        end_at: datetime,
        limit: int | None = None,
        session: str | None = None,
    ) -> list[MarketBar]:
        if timespan == "day" and multiplier == 1:
            return await self.list_day_bars(ticker=ticker, start_at=start_at, end_at=end_at, limit=limit)
        if timespan == "minute" and multiplier == 1:
            return await self.list_minute_bars(
                ticker=ticker,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
                session=session,
            )
        if timespan == "minute" and multiplier > 1:
            return await self.list_minute_agg_bars(
                ticker=ticker,
                multiplier=multiplier,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
            )
        return []

    async def get_range_coverage(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
    ) -> tuple[datetime, datetime] | None:
        if timespan == "day" and multiplier == 1:
            return await self.get_day_range_coverage(ticker=ticker)
        if timespan == "minute" and multiplier == 1:
            return await self.get_minute_range_coverage(ticker=ticker)
        if timespan == "minute" and multiplier > 1:
            return await self.get_minute_agg_range_coverage(ticker=ticker, multiplier=multiplier)
        return None

    async def upsert_bars(self, bars: list[MarketBar]) -> None:
        if not bars:
            return

        first = bars[0]
        if first.timespan == "day" and first.multiplier == 1:
            await self.upsert_day_bars(bars)
            return
        if first.timespan == "minute" and first.multiplier == 1:
            await self.upsert_minute_bars(bars)
            return
        if first.timespan == "minute" and first.multiplier > 1:
            await self.upsert_minute_agg_bars(bars)
            return


def _update_columns(
    stmt,
    columns: list[str],
    *,
    monotonic_true_columns: set[str] | None = None,
) -> dict[str, object]:
    monotonic = monotonic_true_columns or set()
    updates: dict[str, object] = {}
    for column in columns:
        incoming = getattr(stmt.excluded, column)
        if column in monotonic:
            updates[column] = stmt.table.c[column].is_(True) | incoming.is_(True)
            continue
        updates[column] = incoming
    return updates


_POSTGRES_MAX_BIND_PARAMS = 65535
_INSERT_PARAM_HEADROOM = 5000


def _chunk_insert_payload(payload: list[dict]) -> list[list[dict]]:
    if not payload:
        return []

    columns_per_row = len(payload[0])
    if columns_per_row <= 0:
        return [payload]

    max_params = max(1, _POSTGRES_MAX_BIND_PARAMS - _INSERT_PARAM_HEADROOM)
    max_rows = max(1, max_params // columns_per_row)
    return [payload[i : i + max_rows] for i in range(0, len(payload), max_rows)]


def _to_market_trade_date(start_at: datetime) -> date:
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)
    return start_at.astimezone(_MARKET_TZ).date()


def _minute_session_conditions(*, session: str) -> list[object]:
    local_time = cast(func.timezone(str(_MARKET_TZ), MarketBarMinuteModel.start_at), Time)
    if session == "regular":
        return [local_time >= time(9, 30), local_time < time(16, 0)]
    if session == "pre":
        return [local_time >= time(4, 0), local_time < time(9, 30)]
    if session == "night":
        return [or_(local_time >= time(16, 0), local_time < time(4, 0))]
    return []
