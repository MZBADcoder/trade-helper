from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
import re
from datetime import date, datetime, time, timedelta, timezone

from app.application.market_data.errors import (
    MarketDataRangeTooLargeError,
    MarketDataRateLimitedError,
    MarketDataUpstreamUnavailableError,
)
from app.application.market_data.policy import (
    is_range_too_large,
    normalize_timespan,
)
from app.application.market_data.snapshot_mapper import to_market_snapshot
from app.application.market_data.stream_policy import normalized_delay_minutes
from app.application.market_data.trading_calendar import TradingCalendar
from app.core.config import settings
from app.domain.market_data.aggregation import (
    MARKET_CLOSE_TIME,
    MARKET_OPEN_TIME,
    MARKET_TIMEZONE,
    aggregate_bucket,
    aggregate_minute_bars,
    market_trade_date,
    resolve_current_open_bucket,
)
from app.domain.market_data.schemas import MarketBar, MarketSnapshot
from app.infrastructure.clients.massive import MassiveClient
from app.infrastructure.clients.massive_mapper import map_massive_aggregates_to_market_bars
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_TICKER_PATTERN = re.compile(r"^[A-Z.]{1,15}$")
_SUPPORTED_MINUTE_AGG_MULTIPLIERS = {5, 15, 60}
_SUPPORTED_BAR_SESSIONS = {"regular", "pre", "night"}
_PREMARKET_OPEN_TIME = time(4, 0)
_MAX_TRADING_DAY_BACKTRACK_DAYS = 370


@dataclass(slots=True)
class MarketBarsQueryResult:
    bars: list[MarketBar]
    data_source: str
    partial_range: bool = False


@dataclass(slots=True)
class _BarsQuery:
    ticker: str
    timespan: str
    multiplier: int
    session: str
    start_date: date
    end_date: date
    start_at: datetime
    end_at: datetime
    limit: int | None


@dataclass(slots=True)
class _DailySnapshotBaseline:
    snapshot: MarketSnapshot
    prev_close: float | None


class MarketDataApplicationService:
    def __init__(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        massive_client: MassiveClient | None = None,
        trading_calendar: TradingCalendar | None = None,
    ) -> None:
        self._uow = uow
        self._massive_client = massive_client
        self._trading_calendar = trading_calendar or TradingCalendar(massive_client=massive_client)
        self._baseline_refresh_tasks: dict[tuple[str, str, tuple[tuple[date, date], ...]], asyncio.Task[list[MarketBar]]] = {}
        self._baseline_refresh_tasks_lock = asyncio.Lock()

    async def list_bars(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        session: str = "regular",
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
        enforce_range_limit: bool = False,
    ) -> list[MarketBar]:
        result = await self.list_bars_with_meta(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            session=session,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            enforce_range_limit=enforce_range_limit,
        )
        return result.bars

    async def list_bars_with_meta(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int = 1,
        session: str = "regular",
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
        enforce_range_limit: bool = False,
    ) -> MarketBarsQueryResult:
        await self._trading_calendar.ensure_holiday_cache()
        query = _build_bars_query(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            session=session,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            enforce_range_limit=enforce_range_limit,
            trading_calendar=self._trading_calendar,
        )

        if query.timespan == "day" and query.multiplier == 1:
            return await self._list_day_baseline(query=query)
        if query.timespan == "minute" and query.multiplier == 1:
            return await self._list_minute_baseline(query=query)
        if query.timespan == "minute" and query.multiplier in _SUPPORTED_MINUTE_AGG_MULTIPLIERS:
            return await self._list_minute_aggregated(query=query)
        return await self._list_direct_fallback(query=query)

    async def prefetch_default(self, *, ticker: str) -> None:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required")

        await self._trading_calendar.ensure_holiday_cache()
        today = date.today()
        daily_start = today - timedelta(days=settings.market_data_daily_lookback_days)
        intraday_start = self._trading_calendar.shift_trading_day(
            target_date=today,
            trading_days=-(settings.market_data_intraday_lookback_days - 1),
        )

        await self.list_bars(
            ticker=normalized,
            timespan="day",
            multiplier=1,
            start_date=daily_start,
            end_date=today,
        )
        await self.list_bars(
            ticker=normalized,
            timespan="minute",
            multiplier=1,
            start_date=intraday_start,
            end_date=today,
        )

    async def list_snapshots(self, *, tickers: list[str]) -> list[MarketSnapshot]:
        normalized_tickers = _normalize_tickers(tickers=tickers)
        await self._trading_calendar.ensure_holiday_cache()
        baselines = await self._list_daily_snapshot_baselines(tickers=normalized_tickers)
        snapshots_by_symbol = {symbol: baseline.snapshot for symbol, baseline in baselines.items()}

        now_utc = datetime.now(tz=timezone.utc)
        today = market_trade_date(point=now_utc)
        today_is_trading_day = self._trading_calendar.is_trading_day(target_date=today)
        delay_minutes = normalized_delay_minutes(settings.market_stream_delay_minutes)
        status_point = now_utc - timedelta(minutes=delay_minutes)
        market_open_for_status = self._trading_calendar.is_in_trading_session(point=status_point)
        missing_symbols = [symbol for symbol in normalized_tickers if symbol not in snapshots_by_symbol]
        should_fetch_massive = self._massive_client is not None and (
            today_is_trading_day or bool(missing_symbols)
        )

        if should_fetch_massive:
            request_tickers = normalized_tickers if today_is_trading_day else missing_symbols
            try:
                payload = await self._massive_client.list_snapshots(tickers=request_tickers)
            except Exception as exc:
                if not snapshots_by_symbol:
                    raise _map_market_data_upstream_error(exc) from exc
            else:
                for item in payload:
                    mapped = to_market_snapshot(item)
                    if mapped is None:
                        continue
                    mapped = _with_resolved_market_status(snapshot=mapped, market_open=market_open_for_status)
                    baseline = baselines.get(mapped.ticker)
                    snapshots_by_symbol[mapped.ticker] = _merge_snapshot(
                        baseline=baseline,
                        upstream=mapped,
                        today_is_trading_day=today_is_trading_day,
                    )
        elif not snapshots_by_symbol:
            raise MarketDataUpstreamUnavailableError()

        return [snapshots_by_symbol[symbol] for symbol in normalized_tickers if symbol in snapshots_by_symbol]

    async def list_trading_days(
        self,
        *,
        end_date: date | None,
        count: int,
    ) -> list[date]:
        if count < 1:
            raise ValueError("count must be >= 1")
        resolved_end = end_date or date.today()
        await self._trading_calendar.ensure_holiday_cache()
        return self._trading_calendar.list_recent_trading_days(
            end_date=resolved_end,
            count=count,
        )

    async def is_stream_session_open(
        self,
        *,
        delay_minutes: int,
        now: datetime | None = None,
    ) -> bool:
        await self._trading_calendar.ensure_holiday_cache()
        current = now or datetime.now(tz=timezone.utc)
        effective_delay_minutes = max(0, int(delay_minutes))
        delayed_point = current - timedelta(minutes=effective_delay_minutes)
        return self._trading_calendar.is_in_trading_session(point=delayed_point)

    async def precompute_minute_aggregates(
        self,
        *,
        multiplier: int,
        lookback_trade_days: int = 10,
        now: datetime | None = None,
    ) -> int:
        if multiplier not in _SUPPORTED_MINUTE_AGG_MULTIPLIERS:
            raise ValueError("Unsupported minute aggregation multiplier")
        if lookback_trade_days < 1:
            raise ValueError("lookback_trade_days must be >= 1")

        now = now or datetime.now(tz=timezone.utc)
        end_at = now
        await self._trading_calendar.ensure_holiday_cache()
        keep_from_trade_date = self._trading_calendar.shift_trading_day(
            target_date=market_trade_date(point=now),
            trading_days=-(lookback_trade_days - 1),
        )
        start_at = datetime.combine(keep_from_trade_date, time.min, tzinfo=timezone.utc)

        async with self._uow as uow:
            repo = _require_market_data_repo(uow)
            tickers = await repo.list_minute_tickers(start_at=start_at, end_at=end_at)

            produced = 0
            for ticker in tickers:
                minute_bars = await repo.list_minute_bars(
                    ticker=ticker,
                    start_at=start_at,
                    end_at=end_at,
                    limit=None,
                )
                aggregated = aggregate_minute_bars(
                    ticker=ticker,
                    multiplier=multiplier,
                    bars=minute_bars,
                    source="DB_AGG",
                    now=now,
                    include_unfinished=False,
                )
                if not aggregated:
                    continue
                await repo.upsert_minute_agg_bars(aggregated)
                produced += len(aggregated)

            if produced > 0:
                await uow.commit()
            return produced

    async def enforce_minute_retention(
        self,
        *,
        keep_trade_days: int = 10,
        now: datetime | None = None,
    ) -> dict[str, int]:
        if keep_trade_days < 1:
            raise ValueError("keep_trade_days must be >= 1")

        _ = now

        async with self._uow as uow:
            repo = _require_market_data_repo(uow)
            minute_cutoff_trade_date = _resolve_keep_from_trade_date(
                trade_dates=await repo.list_recent_minute_trade_dates(limit=keep_trade_days),
                keep_trade_days=keep_trade_days,
            )
            agg_cutoff_trade_date = _resolve_keep_from_trade_date(
                trade_dates=await repo.list_recent_minute_agg_trade_dates(limit=keep_trade_days),
                keep_trade_days=keep_trade_days,
            )

            deleted_minute = 0
            if minute_cutoff_trade_date is not None:
                deleted_minute = await repo.delete_minute_bars_before_trade_date(
                    keep_from_trade_date=minute_cutoff_trade_date
                )

            deleted_agg = 0
            if agg_cutoff_trade_date is not None:
                deleted_agg = await repo.delete_minute_agg_before_trade_date(
                    keep_from_trade_date=agg_cutoff_trade_date
                )

            if deleted_minute > 0 or deleted_agg > 0:
                await uow.commit()
            return {
                "minute_deleted": deleted_minute,
                "minute_agg_deleted": deleted_agg,
            }

    @staticmethod
    def _default_start_date(
        *,
        timespan: str,
        end_date: date,
        trading_calendar: TradingCalendar | None = None,
    ) -> date:
        if timespan.strip().lower() == "minute":
            if trading_calendar is not None:
                return trading_calendar.shift_trading_day(
                    target_date=end_date,
                    trading_days=-(settings.market_data_intraday_lookback_days - 1),
                )
            return end_date - timedelta(days=settings.market_data_intraday_lookback_days)
        return end_date - timedelta(days=settings.market_data_daily_lookback_days)

    async def _list_day_baseline(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        now = datetime.now(tz=timezone.utc)
        bars, fetched = await self._refresh_day_baseline(query=query, now=now)
        return MarketBarsQueryResult(
            bars=_apply_limit(bars, limit=query.limit),
            data_source="REST" if fetched else "DB",
            partial_range=False,
        )

    async def _list_minute_baseline(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        now = datetime.now(tz=timezone.utc)
        bars, fetched = await self._refresh_minute_baseline(query=query, now=now)
        return MarketBarsQueryResult(
            bars=_apply_limit(bars, limit=query.limit),
            data_source="REST" if fetched else "DB",
            partial_range=False,
        )

    async def _list_minute_aggregated(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        if query.session != "regular":
            return await self._list_direct_fallback(query=query)

        now = datetime.now(tz=timezone.utc)
        minute_bars, _ = await self._refresh_minute_baseline(query=query, now=now)

        async with self._uow as uow:
            repo = _require_market_data_repo(uow)
            rebuilt_finalized = aggregate_minute_bars(
                ticker=query.ticker,
                multiplier=query.multiplier,
                bars=minute_bars,
                source="DB_AGG",
                now=now,
                include_unfinished=False,
            )
            existing_finalized = await repo.list_minute_agg_bars(
                ticker=query.ticker,
                multiplier=query.multiplier,
                start_at=query.start_at,
                end_at=query.end_at,
                final_only=True,
                limit=None,
            )
            finalized = existing_finalized
            if rebuilt_finalized:
                finalized = _merge_bars_by_start_at(existing=existing_finalized, incoming=rebuilt_finalized)
            if rebuilt_finalized and _bars_differ(existing=existing_finalized, incoming=rebuilt_finalized):
                await repo.upsert_minute_agg_bars(rebuilt_finalized)
                await uow.commit()

            mixed_bucket = None
            if self._trading_calendar.is_trading_day(target_date=market_trade_date(point=now)):
                mixed_bucket = resolve_current_open_bucket(now=now, multiplier=query.multiplier)
            realtime_item: MarketBar | None = None
            if mixed_bucket is not None:
                bucket_start, bucket_end = mixed_bucket
                if _ranges_intersect(
                    left_start=query.start_at,
                    left_end=query.end_at,
                    right_start=bucket_start,
                    right_end=bucket_end,
                ):
                    realtime_cutoff = min(
                        bucket_end,
                        now + timedelta(microseconds=1),
                        query.end_at + timedelta(microseconds=1),
                    )
                    if realtime_cutoff > bucket_start:
                        minute_items = [
                            bar
                            for bar in minute_bars
                            if bucket_start <= bar.start_at < realtime_cutoff
                        ]
                        realtime_item = aggregate_bucket(
                            ticker=query.ticker,
                            multiplier=query.multiplier,
                            bars=minute_items,
                            bucket_start=bucket_start,
                            bucket_end=bucket_end,
                            source="DB_AGG_MIXED",
                            is_final=False,
                        )

            merged = _merge_aggregated_bars(
                finalized=finalized,
                realtime_item=realtime_item,
                start_at=query.start_at,
                end_at=query.end_at,
                limit=query.limit,
            )
            if merged:
                return MarketBarsQueryResult(
                    bars=merged,
                    data_source="DB_AGG_MIXED" if realtime_item is not None else "DB_AGG",
                    partial_range=False,
                )

        if settings.market_data_enable_direct_fallback:
            return await self._list_direct_fallback(query=query)
        return MarketBarsQueryResult(bars=[], data_source="DB_AGG", partial_range=False)

    async def _list_direct_fallback(self, *, query: _BarsQuery) -> MarketBarsQueryResult:
        bars = await self._fetch_from_massive(
            ticker=query.ticker,
            timespan=query.timespan,
            multiplier=query.multiplier,
            start_date=query.start_date,
            end_date=query.end_date,
        )
        if query.timespan == "minute":
            bars = _filter_bars_by_range(
                bars=bars,
                start_at=query.start_at,
                end_at=query.end_at,
            )
            bars = _filter_bars_by_session(bars=bars, session=query.session)
        return MarketBarsQueryResult(
            bars=_apply_limit(bars, limit=query.limit),
            data_source="REST",
            partial_range=False,
        )

    async def _refresh_day_baseline(
        self,
        *,
        query: _BarsQuery,
        now: datetime,
    ) -> tuple[list[MarketBar], bool]:
        async with self._uow as uow:
            repo = _require_market_data_repo(uow)
            existing = await repo.list_day_bars(
                ticker=query.ticker,
                start_at=query.start_at,
                end_at=query.end_at,
                limit=None,
            )
            refresh_windows = _resolve_day_refresh_windows(
                query=query,
                existing_bars=existing,
                now=now,
                trading_calendar=self._trading_calendar,
            )

        if not refresh_windows:
            return existing, False

        async def _refresh() -> list[MarketBar]:
            fetched = await self._fetch_baseline_windows(
                ticker=query.ticker,
                timespan="day",
                refresh_windows=refresh_windows,
            )
            if not fetched:
                return []

            refreshed = _with_day_finality(
                bars=fetched,
                now=now,
                trading_calendar=self._trading_calendar,
                finalize_trade_days=_day_finalize_trade_days(),
            )
            async with self._uow as refresh_uow:
                refresh_repo = _require_market_data_repo(refresh_uow)
                await refresh_repo.upsert_day_bars(refreshed)
                await refresh_uow.commit()
            return refreshed

        try:
            refreshed = await self._run_baseline_refresh_once(
                key=_baseline_refresh_key(
                    ticker=query.ticker,
                    timespan="day",
                    refresh_windows=refresh_windows,
                ),
                work=_refresh,
            )
        except (MarketDataRateLimitedError, MarketDataUpstreamUnavailableError):
            if _has_complete_day_cache(
                query=query,
                bars=existing,
                trading_calendar=self._trading_calendar,
            ):
                return existing, False
            raise
        if not refreshed:
            return existing, False

        incoming = _filter_bars_by_range(
            bars=refreshed,
            start_at=query.start_at,
            end_at=query.end_at,
        )
        return _merge_bars_by_start_at(existing=existing, incoming=incoming), True

    async def _refresh_minute_baseline(
        self,
        *,
        query: _BarsQuery,
        now: datetime,
    ) -> tuple[list[MarketBar], bool]:
        async with self._uow as uow:
            repo = _require_market_data_repo(uow)
            existing = await repo.list_minute_bars(
                ticker=query.ticker,
                start_at=query.start_at,
                end_at=query.end_at,
                limit=None,
                session=query.session,
            )
            refresh_windows = _resolve_minute_refresh_windows(
                query=query,
                existing_bars=existing,
                now=now,
                trading_calendar=self._trading_calendar,
            )

        if not refresh_windows:
            return existing, False

        async def _refresh() -> list[MarketBar]:
            fetched = await self._fetch_baseline_windows(
                ticker=query.ticker,
                timespan="minute",
                refresh_windows=refresh_windows,
            )
            if not fetched:
                return []

            refreshed = _with_minute_finality(
                bars=fetched,
                now=now,
                finalize_delay_minutes=_minute_finalize_delay_minutes(),
            )
            async with self._uow as refresh_uow:
                refresh_repo = _require_market_data_repo(refresh_uow)
                await refresh_repo.upsert_minute_bars(refreshed)
                await refresh_uow.commit()
            return refreshed

        try:
            refreshed = await self._run_baseline_refresh_once(
                key=_baseline_refresh_key(
                    ticker=query.ticker,
                    timespan="minute",
                    refresh_windows=refresh_windows,
                ),
                work=_refresh,
            )
        except (MarketDataRateLimitedError, MarketDataUpstreamUnavailableError):
            if _has_complete_minute_cache(
                query=query,
                bars=existing,
                now=now,
                trading_calendar=self._trading_calendar,
            ):
                return existing, False
            raise
        if not refreshed:
            return existing, False

        incoming = _filter_bars_by_session(
            bars=_filter_bars_by_range(
                bars=refreshed,
                start_at=query.start_at,
                end_at=query.end_at,
            ),
            session=query.session,
        )
        return _merge_bars_by_start_at(existing=existing, incoming=incoming), True

    async def _fetch_baseline_windows(
        self,
        *,
        ticker: str,
        timespan: str,
        refresh_windows: list[tuple[date, date]],
    ) -> list[MarketBar]:
        fetched: list[MarketBar] = []
        for start_date, end_date in refresh_windows:
            incoming = await self._fetch_from_massive(
                ticker=ticker,
                timespan=timespan,
                multiplier=1,
                start_date=start_date,
                end_date=end_date,
            )
            if incoming:
                fetched = _merge_bars_by_start_at(existing=fetched, incoming=incoming)
        return fetched

    async def _run_baseline_refresh_once(
        self,
        *,
        key: tuple[str, str, tuple[tuple[date, date], ...]],
        work: Callable[[], Awaitable[list[MarketBar]]],
    ) -> list[MarketBar]:
        async with self._baseline_refresh_tasks_lock:
            task = self._baseline_refresh_tasks.get(key)
            if task is None:
                task = asyncio.create_task(work())
                self._baseline_refresh_tasks[key] = task
                task.add_done_callback(
                    lambda completed, refresh_key=key: asyncio.create_task(
                        self._clear_baseline_refresh_task(
                            key=refresh_key,
                            task=completed,
                        )
                    )
                )
        assert task is not None
        return await asyncio.shield(task)

    async def _clear_baseline_refresh_task(
        self,
        *,
        key: tuple[str, str, tuple[tuple[date, date], ...]],
        task: asyncio.Task[list[MarketBar]],
    ) -> None:
        async with self._baseline_refresh_tasks_lock:
            if self._baseline_refresh_tasks.get(key) is task:
                self._baseline_refresh_tasks.pop(key, None)

    async def _fetch_from_massive(
        self,
        *,
        ticker: str,
        timespan: str,
        multiplier: int,
        start_date: date,
        end_date: date,
    ) -> list[MarketBar]:
        if self._massive_client is None:
            raise MarketDataUpstreamUnavailableError()
        try:
            aggregates = await self._massive_client.list_aggs(
                ticker=ticker,
                multiplier=multiplier,
                timespan=timespan,
                from_date=start_date.isoformat(),
                to_date=end_date.isoformat(),
                adjusted=True,
                sort="asc",
                limit=50000,
            )
        except Exception as exc:
            raise _map_market_data_upstream_error(exc) from exc
        return map_massive_aggregates_to_market_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            aggregates=aggregates,
        )

    async def _list_daily_snapshot_baselines(self, *, tickers: list[str]) -> dict[str, _DailySnapshotBaseline]:
        baselines: dict[str, _DailySnapshotBaseline] = {}
        async with self._uow as uow:
            repo = getattr(uow, "market_data_repo", None)
            if repo is None:
                return baselines

            for symbol in tickers:
                list_recent = getattr(repo, "list_recent_day_bars", None)
                if list_recent is None:
                    continue
                day_bars = await list_recent(ticker=symbol, limit=2)
                if not day_bars:
                    continue

                latest = day_bars[-1]
                previous = day_bars[-2] if len(day_bars) > 1 else None
                prev_close = previous.close if previous is not None else None
                change, change_pct = _calc_change(
                    current=latest.close,
                    previous=prev_close,
                )
                baselines[symbol] = _DailySnapshotBaseline(
                    snapshot=MarketSnapshot(
                        ticker=symbol,
                        last=latest.close,
                        change=change,
                        change_pct=change_pct,
                        open=latest.open,
                        high=latest.high,
                        low=latest.low,
                        volume=int(latest.volume),
                        updated_at=latest.start_at,
                        market_status="closed",
                        source="DB",
                    ),
                    prev_close=prev_close,
                )
        return baselines


def _merge_snapshot(
    *,
    baseline: _DailySnapshotBaseline | None,
    upstream: MarketSnapshot,
    today_is_trading_day: bool,
) -> MarketSnapshot:
    if baseline is None:
        return upstream

    if not today_is_trading_day:
        last = upstream.last if upstream.last > 0 else baseline.snapshot.last
        return MarketSnapshot(
            ticker=upstream.ticker,
            last=last,
            change=baseline.snapshot.change,
            change_pct=baseline.snapshot.change_pct,
            open=baseline.snapshot.open,
            high=baseline.snapshot.high,
            low=baseline.snapshot.low,
            volume=baseline.snapshot.volume,
            updated_at=max(upstream.updated_at, baseline.snapshot.updated_at),
            market_status=upstream.market_status,
            source=upstream.source,
        )

    if baseline.prev_close is not None and upstream.last > 0 and upstream.change == 0 and upstream.change_pct == 0:
        change, change_pct = _calc_change(
            current=upstream.last,
            previous=baseline.prev_close,
        )
        return MarketSnapshot(
            ticker=upstream.ticker,
            last=upstream.last,
            change=change,
            change_pct=change_pct,
            open=upstream.open,
            high=upstream.high,
            low=upstream.low,
            volume=upstream.volume,
            updated_at=upstream.updated_at,
            market_status=upstream.market_status,
            source=upstream.source,
        )

    return upstream


def _calc_change(*, current: float, previous: float | None) -> tuple[float, float]:
    if previous is None or previous == 0:
        return 0.0, 0.0
    change = current - previous
    change_pct = (change / previous) * 100
    return change, change_pct


def _with_resolved_market_status(*, snapshot: MarketSnapshot, market_open: bool) -> MarketSnapshot:
    normalized = snapshot.market_status.strip().lower()
    if normalized and normalized != "unknown":
        return snapshot

    return replace(snapshot, market_status="open" if market_open else "closed")


def _build_bars_query(
    *,
    ticker: str,
    timespan: str,
    multiplier: int,
    session: str,
    start_date: date | None,
    end_date: date | None,
    limit: int | None,
    enforce_range_limit: bool,
    trading_calendar: TradingCalendar | None,
) -> _BarsQuery:
    has_explicit_start = start_date is not None
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = MarketDataApplicationService._default_start_date(
            timespan=timespan,
            end_date=end_date,
            trading_calendar=trading_calendar,
        )

    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError("Ticker is required")

    normalized_timespan = normalize_timespan(timespan)
    if not normalized_timespan:
        raise ValueError("Timespan is required")
    normalized_session = _normalize_session(session=session)

    if multiplier < 1:
        raise ValueError("Multiplier must be >= 1")
    if end_date < start_date:
        raise ValueError("End date must be on or after start date")
    if enforce_range_limit and has_explicit_start:
        if is_range_too_large(
            timespan=normalized_timespan,
            multiplier=multiplier,
            start_date=start_date,
            end_date=end_date,
            trading_calendar=trading_calendar,
        ):
            raise MarketDataRangeTooLargeError()

    if normalized_timespan == "minute":
        start_at, end_at = _minute_query_bounds_utc(
            start_date=start_date,
            end_date=end_date,
            session=normalized_session,
        )
    else:
        start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_at = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    return _BarsQuery(
        ticker=normalized_ticker,
        timespan=normalized_timespan,
        multiplier=multiplier,
        session=normalized_session,
        start_date=start_date,
        end_date=end_date,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )


def _require_market_data_repo(uow: SqlAlchemyUnitOfWork):
    if uow.market_data_repo is None:
        raise RuntimeError("Market data repository not configured")
    return uow.market_data_repo


def _resolve_day_refresh_windows(
    *,
    query: _BarsQuery,
    existing_bars: list[MarketBar],
    now: datetime,
    trading_calendar: TradingCalendar,
) -> list[tuple[date, date]]:
    finalize_trade_days = _day_finalize_trade_days()
    existing_by_trade_date = {_day_bar_trade_date(start_at=bar.start_at): bar for bar in existing_bars}
    refresh_dates: list[date] = []
    for trade_date in _list_query_trade_dates(
        start_date=query.start_date,
        end_date=query.end_date,
        trading_calendar=trading_calendar,
    ):
        current = existing_by_trade_date.get(trade_date)
        if current is None:
            refresh_dates.append(trade_date)
            continue
        if not _is_day_trade_date_final_state_valid(
            current=current,
            trade_date=trade_date,
            now=now,
            trading_calendar=trading_calendar,
            finalize_trade_days=finalize_trade_days,
        ):
            refresh_dates.append(trade_date)
            continue
        if _is_day_trade_date_refresh_due(
            current=current,
            trade_date=trade_date,
            now=now,
            trading_calendar=trading_calendar,
            finalize_trade_days=finalize_trade_days,
        ):
            refresh_dates.append(trade_date)
    return _group_contiguous_dates(dates=refresh_dates)


def _resolve_minute_refresh_windows(
    *,
    query: _BarsQuery,
    existing_bars: list[MarketBar],
    now: datetime,
    trading_calendar: TradingCalendar,
) -> list[tuple[date, date]]:
    finalize_delay_minutes = _minute_finalize_delay_minutes()
    existing_by_trade_date: dict[date, list[MarketBar]] = {}
    for bar in existing_bars:
        trade_date = market_trade_date(point=bar.start_at)
        existing_by_trade_date.setdefault(trade_date, []).append(bar)

    refresh_dates: list[date] = []
    for trade_date in _list_query_trade_dates(
        start_date=query.start_date,
        end_date=query.end_date,
        trading_calendar=trading_calendar,
    ):
        items = existing_by_trade_date.get(trade_date, [])
        if not items:
            if (
                _expected_minute_session_bar_count(
                    session=query.session,
                    trade_date=trade_date,
                    trading_calendar=trading_calendar,
                    now=now,
                )
                > 0
            ):
                refresh_dates.append(trade_date)
            continue
        if any(
            not _is_minute_bar_final_state_valid(
                bar=bar,
                now=now,
                finalize_delay_minutes=finalize_delay_minutes,
            )
            for bar in items
        ):
            refresh_dates.append(trade_date)
            continue
        if not _has_complete_minute_session_cache(
            session=query.session,
            trade_date=trade_date,
            bars=items,
            trading_calendar=trading_calendar,
            now=now,
        ):
            refresh_dates.append(trade_date)
            continue
        if _is_minute_session_trade_date_mutable(
            session=query.session,
            trade_date=trade_date,
            now=now,
        ):
            refresh_dates.append(trade_date)
    return _group_contiguous_dates(dates=refresh_dates)


def _with_day_finality(
    *,
    bars: list[MarketBar],
    now: datetime,
    trading_calendar: TradingCalendar,
    finalize_trade_days: int,
) -> list[MarketBar]:
    return [
        replace(
            bar,
            is_final=_is_day_trade_date_confirmation_due(
                trade_date=_day_bar_trade_date(start_at=bar.start_at),
                now=now,
                trading_calendar=trading_calendar,
                finalize_trade_days=finalize_trade_days,
            ),
        )
        for bar in bars
    ]


def _with_minute_finality(
    *,
    bars: list[MarketBar],
    now: datetime,
    finalize_delay_minutes: int,
) -> list[MarketBar]:
    return [
        replace(
            bar,
            is_final=_is_minute_bar_confirmation_due(
                bar=bar,
                now=now,
                finalize_delay_minutes=finalize_delay_minutes,
            ),
        )
        for bar in bars
    ]


def _bars_differ(*, existing: list[MarketBar], incoming: list[MarketBar]) -> bool:
    if len(existing) != len(incoming):
        return True
    return [_bar_signature(bar) for bar in existing] != [_bar_signature(bar) for bar in incoming]


def _bar_signature(bar: MarketBar) -> tuple[object, ...]:
    return (
        bar.start_at,
        bar.end_at,
        bar.is_final,
        _round_float(bar.open),
        _round_float(bar.high),
        _round_float(bar.low),
        _round_float(bar.close),
        _round_float(bar.volume),
        _round_optional_float(bar.vwap),
        bar.trades,
    )


def _round_float(value: float) -> float:
    return round(float(value), 10)


def _round_optional_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 10)


def _list_query_trade_dates(
    *,
    start_date: date,
    end_date: date,
    trading_calendar: TradingCalendar,
) -> list[date]:
    result: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        if trading_calendar.is_trading_day(target_date=cursor):
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def _group_contiguous_dates(*, dates: list[date]) -> list[tuple[date, date]]:
    ordered = sorted(set(dates))
    if not ordered:
        return []

    windows: list[tuple[date, date]] = []
    start = ordered[0]
    end = ordered[0]
    for current in ordered[1:]:
        if current == end + timedelta(days=1):
            end = current
            continue
        windows.append((start, end))
        start = current
        end = current
    windows.append((start, end))
    return windows


def _baseline_refresh_key(
    *,
    ticker: str,
    timespan: str,
    refresh_windows: list[tuple[date, date]],
) -> tuple[str, str, tuple[tuple[date, date], ...]]:
    return ticker, timespan, tuple(refresh_windows)


def _day_bar_trade_date(*, start_at: datetime) -> date:
    if start_at.tzinfo is None:
        return start_at.date()
    return start_at.astimezone(timezone.utc).date()


def _day_finalize_trade_days() -> int:
    return max(1, int(settings.market_data_day_finalize_trade_days))


def _minute_finalize_delay_minutes() -> int:
    return normalized_delay_minutes(settings.market_data_minute_finalize_delay_minutes)


def _is_day_trade_date_final_state_valid(
    *,
    current: MarketBar,
    trade_date: date,
    now: datetime,
    trading_calendar: TradingCalendar,
    finalize_trade_days: int,
) -> bool:
    should_be_final = _is_day_trade_date_confirmation_due(
        trade_date=trade_date,
        now=now,
        trading_calendar=trading_calendar,
        finalize_trade_days=finalize_trade_days,
    )
    return current.is_final is should_be_final


def _is_day_trade_date_refresh_due(
    *,
    current: MarketBar,
    trade_date: date,
    now: datetime,
    trading_calendar: TradingCalendar,
    finalize_trade_days: int,
) -> bool:
    if current.is_final is not True:
        return _is_day_trade_date_current(
            trade_date=trade_date,
            now=now,
            trading_calendar=trading_calendar,
        ) or _is_day_trade_date_confirmation_due(
            trade_date=trade_date,
            now=now,
            trading_calendar=trading_calendar,
            finalize_trade_days=finalize_trade_days,
        )
    return not _is_day_trade_date_confirmation_due(
        trade_date=trade_date,
        now=now,
        trading_calendar=trading_calendar,
        finalize_trade_days=finalize_trade_days,
    )


def _is_day_trade_date_current(
    *,
    trade_date: date,
    now: datetime,
    trading_calendar: TradingCalendar,
) -> bool:
    return trade_date == _align_on_or_before(
        target_date=market_trade_date(point=now),
        trading_calendar=trading_calendar,
    )


def _is_day_trade_date_confirmation_due(
    *,
    trade_date: date,
    now: datetime,
    trading_calendar: TradingCalendar,
    finalize_trade_days: int,
) -> bool:
    current_trade_date = _align_on_or_before(
        target_date=market_trade_date(point=now),
        trading_calendar=trading_calendar,
    )
    confirmation_trade_date = trading_calendar.shift_trading_day(
        target_date=trade_date,
        trading_days=finalize_trade_days,
    )
    return current_trade_date >= confirmation_trade_date


def _align_on_or_before(*, target_date: date, trading_calendar: TradingCalendar) -> date:
    align = getattr(trading_calendar, "align_on_or_before", None)
    if callable(align):
        return align(target_date=target_date)

    cursor = target_date
    for _ in range(_MAX_TRADING_DAY_BACKTRACK_DAYS):
        if trading_calendar.is_trading_day(target_date=cursor):
            return cursor
        cursor -= timedelta(days=1)
    raise ValueError("Trading calendar could not align target date on or before requested date")


def _is_minute_bar_final_state_valid(
    *,
    bar: MarketBar,
    now: datetime,
    finalize_delay_minutes: int,
) -> bool:
    should_be_final = _is_minute_bar_confirmation_due(
        bar=bar,
        now=now,
        finalize_delay_minutes=finalize_delay_minutes,
    )
    return bar.is_final is should_be_final


def _is_minute_bar_confirmation_due(
    *,
    bar: MarketBar,
    now: datetime,
    finalize_delay_minutes: int,
) -> bool:
    end_at = bar.start_at + timedelta(minutes=bar.multiplier)
    confirmation_at = max(
        end_at,
        bar.start_at + timedelta(minutes=finalize_delay_minutes),
    )
    return confirmation_at <= now


def _is_minute_session_trade_date_mutable(
    *,
    session: str,
    trade_date: date,
    now: datetime,
) -> bool:
    if trade_date != market_trade_date(point=now):
        return False

    local_time = now.astimezone(MARKET_TIMEZONE).time()
    if session == "regular":
        return MARKET_OPEN_TIME <= local_time < MARKET_CLOSE_TIME
    if session == "pre":
        return _PREMARKET_OPEN_TIME <= local_time < MARKET_OPEN_TIME
    if session == "night":
        return local_time >= MARKET_CLOSE_TIME or local_time < _PREMARKET_OPEN_TIME
    return False


def _has_complete_minute_session_cache(
    *,
    session: str,
    trade_date: date,
    bars: list[MarketBar],
    trading_calendar: TradingCalendar,
    now: datetime | None = None,
) -> bool:
    expected = _expected_minute_session_bar_count(
        session=session,
        trade_date=trade_date,
        trading_calendar=trading_calendar,
        now=now,
    )
    if expected <= 0:
        return True
    observed = {bar.start_at for bar in bars}
    return len(observed) >= expected


def _expected_minute_session_bar_count(
    *,
    session: str,
    trade_date: date,
    trading_calendar: TradingCalendar,
    now: datetime | None = None,
) -> int:
    if now is not None and trade_date == market_trade_date(point=now):
        local_now = now.astimezone(MARKET_TIMEZONE)
        if session == "regular":
            session_bounds = trading_calendar.session_bounds(target_date=trade_date)
            if session_bounds is None:
                opened_at = datetime.combine(trade_date, MARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
                closed_at = datetime.combine(trade_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE)
            else:
                opened_at, closed_at = session_bounds
            return _completed_session_minutes(start_at=opened_at, end_at=closed_at, point=local_now)
        if session == "pre":
            opened_at = datetime.combine(trade_date, _PREMARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
            closed_at = datetime.combine(trade_date, MARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
            return _completed_session_minutes(start_at=opened_at, end_at=closed_at, point=local_now)
        if session == "night":
            overnight_start = datetime.combine(trade_date, time.min, tzinfo=MARKET_TIMEZONE)
            overnight_end = datetime.combine(trade_date, _PREMARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
            post_close_start = datetime.combine(trade_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE)
            post_close_end = datetime.combine(trade_date + timedelta(days=1), time.min, tzinfo=MARKET_TIMEZONE)
            return _completed_session_minutes(
                start_at=overnight_start,
                end_at=overnight_end,
                point=local_now,
            ) + _completed_session_minutes(
                start_at=post_close_start,
                end_at=post_close_end,
                point=local_now,
            )
    if session == "regular":
        session_bounds = trading_calendar.session_bounds(target_date=trade_date)
        if session_bounds is None:
            opened_at = datetime.combine(trade_date, MARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
            closed_at = datetime.combine(trade_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE)
        else:
            opened_at, closed_at = session_bounds
        return max(0, int((closed_at - opened_at).total_seconds() // 60))
    if session == "pre":
        return 330
    if session == "night":
        return 720
    return 0


def _completed_session_minutes(*, start_at: datetime, end_at: datetime, point: datetime) -> int:
    if point <= start_at:
        return 0
    effective_end = min(point, end_at)
    if effective_end <= start_at:
        return 0
    return max(0, int((effective_end - start_at).total_seconds() // 60))


def _has_complete_day_cache(
    *,
    query: _BarsQuery,
    bars: list[MarketBar],
    trading_calendar: TradingCalendar,
) -> bool:
    expected = set(
        _list_query_trade_dates(
            start_date=query.start_date,
            end_date=query.end_date,
            trading_calendar=trading_calendar,
        )
    )
    observed = {_day_bar_trade_date(start_at=bar.start_at) for bar in bars}
    return expected.issubset(observed)


def _has_complete_minute_cache(
    *,
    query: _BarsQuery,
    bars: list[MarketBar],
    now: datetime,
    trading_calendar: TradingCalendar,
) -> bool:
    by_trade_date: dict[date, list[MarketBar]] = {}
    for bar in bars:
        trade_date = market_trade_date(point=bar.start_at)
        by_trade_date.setdefault(trade_date, []).append(bar)

    for trade_date in _list_query_trade_dates(
        start_date=query.start_date,
        end_date=query.end_date,
        trading_calendar=trading_calendar,
    ):
        items = by_trade_date.get(trade_date, [])
        if not _has_complete_minute_session_cache(
            session=query.session,
            trade_date=trade_date,
            bars=items,
            trading_calendar=trading_calendar,
            now=now,
        ):
            return False
    return True


def _ranges_intersect(
    *,
    left_start: datetime,
    left_end: datetime,
    right_start: datetime,
    right_end: datetime,
) -> bool:
    return left_start < right_end and right_start <= left_end


def _merge_aggregated_bars(
    *,
    finalized: list[MarketBar],
    realtime_item: MarketBar | None,
    start_at: datetime,
    end_at: datetime,
    limit: int | None,
) -> list[MarketBar]:
    merged = [bar for bar in finalized if start_at <= bar.start_at <= end_at]
    if realtime_item is not None and start_at <= realtime_item.start_at <= end_at:
        merged = [bar for bar in merged if bar.start_at != realtime_item.start_at]
        merged.append(realtime_item)

    merged.sort(key=lambda bar: bar.start_at)
    return _apply_limit(merged, limit=limit)


def _apply_limit(bars: list[MarketBar], *, limit: int | None) -> list[MarketBar]:
    if not limit or limit < 1:
        return bars
    return bars[:limit]


def _merge_bars_by_start_at(*, existing: list[MarketBar], incoming: list[MarketBar]) -> list[MarketBar]:
    merged = {bar.start_at: bar for bar in existing}
    for bar in incoming:
        merged[bar.start_at] = bar
    return sorted(merged.values(), key=lambda bar: bar.start_at)


def _minute_query_bounds_utc(*, start_date: date, end_date: date, session: str) -> tuple[datetime, datetime]:
    if session == "pre":
        pre_start = datetime.combine(start_date, _PREMARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
        pre_end = datetime.combine(end_date, MARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE) - timedelta(minutes=1)
        return pre_start.astimezone(timezone.utc), pre_end.astimezone(timezone.utc)
    if session == "night":
        # Include both post-close and early-morning segments for each selected date.
        night_start = datetime.combine(start_date, time.min, tzinfo=MARKET_TIMEZONE)
        night_end = datetime.combine(end_date, time.max, tzinfo=MARKET_TIMEZONE)
        return night_start.astimezone(timezone.utc), night_end.astimezone(timezone.utc)

    market_start = datetime.combine(start_date, MARKET_OPEN_TIME, tzinfo=MARKET_TIMEZONE)
    market_close = datetime.combine(end_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE)
    market_last_bar_start = market_close - timedelta(minutes=1)
    return market_start.astimezone(timezone.utc), market_last_bar_start.astimezone(timezone.utc)


def _normalize_session(*, session: str) -> str:
    normalized = session.strip().lower()
    if normalized not in _SUPPORTED_BAR_SESSIONS:
        raise ValueError("session must be one of: regular, pre, night")
    return normalized


def _filter_bars_by_session(*, bars: list[MarketBar], session: str) -> list[MarketBar]:
    return [bar for bar in bars if _is_bar_in_session(bar=bar, session=session)]


def _filter_bars_by_range(*, bars: list[MarketBar], start_at: datetime, end_at: datetime) -> list[MarketBar]:
    return [bar for bar in bars if start_at <= bar.start_at <= end_at]


def _is_bar_in_session(*, bar: MarketBar, session: str) -> bool:
    local_time = bar.start_at.astimezone(MARKET_TIMEZONE).time()
    if session == "regular":
        return MARKET_OPEN_TIME <= local_time < MARKET_CLOSE_TIME
    if session == "pre":
        return _PREMARKET_OPEN_TIME <= local_time < MARKET_OPEN_TIME
    if session == "night":
        return local_time >= MARKET_CLOSE_TIME or local_time < _PREMARKET_OPEN_TIME
    return False


def _resolve_keep_from_trade_date(*, trade_dates: list[date], keep_trade_days: int) -> date | None:
    if keep_trade_days < 1 or len(trade_dates) < keep_trade_days:
        return None
    ordered = sorted(set(trade_dates), reverse=True)
    if len(ordered) < keep_trade_days:
        return None
    return ordered[keep_trade_days - 1]


def _normalize_tickers(*, tickers: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        if not _TICKER_PATTERN.fullmatch(symbol):
            raise ValueError("MARKET_DATA_INVALID_TICKERS")
        if symbol not in seen:
            seen.add(symbol)
            unique.append(symbol)

    if not unique or len(unique) > 50:
        raise ValueError("MARKET_DATA_INVALID_TICKERS")
    return unique


def _map_market_data_upstream_error(exc: Exception) -> ValueError:
    detail = str(exc).strip()
    if detail == "MARKET_DATA_RATE_LIMITED":
        return MarketDataRateLimitedError()
    if detail == "MARKET_DATA_UPSTREAM_UNAVAILABLE":
        return MarketDataUpstreamUnavailableError()

    lowered = detail.lower()
    if "rate limit" in lowered or "429" in lowered:
        return MarketDataRateLimitedError()
    return MarketDataUpstreamUnavailableError()
