from __future__ import annotations

from functools import lru_cache
import os
import socket

from app.application.auth.service import AuthApplicationService
from app.application.market_data.realtime_publisher import StockMarketRealtimePublisher
from app.application.market_data.service import MarketDataApplicationService
from app.application.market_data.stream_hub import StockMarketStreamHub
from app.application.options.service import OptionsApplicationService
from app.application.watchlist.service import WatchlistApplicationService
from app.core.config import settings
from app.infrastructure.clients.massive import MassiveClient
from app.infrastructure.clients.massive_stream import MassiveStocksWebSocketClient
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.streaming.redis_event_bus import (
    RedisMarketEventPublisher,
    RedisMarketEventSubscriber,
)
from app.infrastructure.streaming.redis_topic_registry import RedisMarketTopicRegistry


@lru_cache
def _massive_client() -> MassiveClient | None:
    if not settings.massive_api_key:
        return None
    return MassiveClient(settings.massive_api_key)


def build_uow() -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory=SessionLocal)


def build_market_data_service() -> MarketDataApplicationService:
    return MarketDataApplicationService(
        uow=build_uow(),
        massive_client=_massive_client(),
    )


def build_watchlist_service() -> WatchlistApplicationService:
    return WatchlistApplicationService(
        uow=build_uow(),
        market_data_service=build_market_data_service(),
    )


def build_options_service() -> OptionsApplicationService:
    return OptionsApplicationService(
        massive_client=_massive_client(),
        enabled=settings.options_data_enabled,
    )


def build_auth_service() -> AuthApplicationService:
    return AuthApplicationService(uow=build_uow())


@lru_cache
def _massive_stocks_stream_client() -> MassiveStocksWebSocketClient | None:
    if not settings.massive_api_key:
        return None
    return MassiveStocksWebSocketClient(api_key=settings.massive_api_key)


@lru_cache
def _redis_market_event_publisher() -> RedisMarketEventPublisher:
    return RedisMarketEventPublisher(
        redis_url=settings.redis_url,
        channel=settings.market_stream_redis_channel,
    )


@lru_cache
def _redis_market_event_subscriber() -> RedisMarketEventSubscriber:
    return RedisMarketEventSubscriber(
        redis_url=settings.redis_url,
        channel=settings.market_stream_redis_channel,
    )


@lru_cache
def _redis_market_topic_registry() -> RedisMarketTopicRegistry:
    return RedisMarketTopicRegistry(
        redis_url=settings.redis_url,
        key_prefix=settings.market_stream_registry_prefix,
        ttl_seconds=settings.market_stream_registry_ttl_seconds,
    )


def _resolve_market_stream_gateway_instance_id() -> str:
    configured = (settings.market_stream_gateway_instance_id or "").strip()
    if configured:
        return configured
    return f"{socket.gethostname()}-{os.getpid()}"


@lru_cache
def _market_stream_hub() -> StockMarketStreamHub:
    return StockMarketStreamHub(
        event_subscriber=_redis_market_event_subscriber(),
        topic_registry=_redis_market_topic_registry(),
        instance_id=_resolve_market_stream_gateway_instance_id(),
        max_symbols_per_connection=settings.market_stream_max_symbols_per_connection,
        queue_size=settings.market_stream_queue_size,
        registry_refresh_seconds=settings.market_stream_registry_refresh_seconds,
    )


def build_market_stream_hub() -> StockMarketStreamHub:
    return _market_stream_hub()


@lru_cache
def _stock_market_realtime_publisher() -> StockMarketRealtimePublisher:
    return StockMarketRealtimePublisher(
        upstream_client=_massive_stocks_stream_client(),
        event_publisher=_redis_market_event_publisher(),
        topic_registry=_redis_market_topic_registry(),
        reconcile_interval_seconds=settings.market_stream_realtime_reconcile_interval_seconds,
    )


def build_stock_market_realtime_publisher() -> StockMarketRealtimePublisher:
    return _stock_market_realtime_publisher()


async def shutdown_market_stream_hub() -> None:
    if _market_stream_hub.cache_info().currsize == 0:
        return
    hub = _market_stream_hub()
    await hub.shutdown()
    if _stock_market_realtime_publisher.cache_info().currsize == 0 and _redis_market_topic_registry.cache_info().currsize > 0:
        registry = _redis_market_topic_registry()
        await registry.close()
        _redis_market_topic_registry.cache_clear()
    _market_stream_hub.cache_clear()
    _redis_market_event_subscriber.cache_clear()


async def shutdown_stock_market_realtime_publisher() -> None:
    if _stock_market_realtime_publisher.cache_info().currsize == 0:
        return
    publisher = _stock_market_realtime_publisher()
    await publisher.shutdown()
    _stock_market_realtime_publisher.cache_clear()
    _massive_stocks_stream_client.cache_clear()
    _redis_market_event_publisher.cache_clear()
    _redis_market_topic_registry.cache_clear()
