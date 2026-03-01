from __future__ import annotations

from app.application.container import build_market_data_service
from app.core.celery_app import celery_app
from app.core.config import settings
from app.tasks.async_runtime import run_async_task


@celery_app.task(name="app.tasks.market_data.aggregate_minute_bars_5m")
def aggregate_minute_bars_5m() -> dict[str, int]:
    return run_async_task(_aggregate_minute_bars(multiplier=5))


@celery_app.task(name="app.tasks.market_data.aggregate_minute_bars_15m")
def aggregate_minute_bars_15m() -> dict[str, int]:
    return run_async_task(_aggregate_minute_bars(multiplier=15))


@celery_app.task(name="app.tasks.market_data.aggregate_minute_bars_60m")
def aggregate_minute_bars_60m() -> dict[str, int]:
    return run_async_task(_aggregate_minute_bars(multiplier=60))


@celery_app.task(name="app.tasks.market_data.prune_minute_bars_retention")
def prune_minute_bars_retention() -> dict[str, int]:
    return run_async_task(_prune_minute_bars_retention())


async def _aggregate_minute_bars(*, multiplier: int) -> dict[str, int]:
    service = build_market_data_service()
    produced = await service.precompute_minute_aggregates(
        multiplier=multiplier,
        lookback_trade_days=settings.market_data_minute_retention_trade_days,
    )
    return {"multiplier": multiplier, "produced": produced}


async def _prune_minute_bars_retention() -> dict[str, int]:
    service = build_market_data_service()
    return await service.enforce_minute_retention(
        keep_trade_days=settings.market_data_minute_retention_trade_days,
    )
