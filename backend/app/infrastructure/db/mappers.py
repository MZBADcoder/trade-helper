from __future__ import annotations

from datetime import date

from app.domain.auth.schemas import User, UserCredentials
from app.domain.market_data.schemas import MarketBar
from app.domain.watchlist.schemas import WatchlistItem
from app.infrastructure.db.models.market_data import (
    MarketBarDayModel,
    MarketBarMinuteAggModel,
    MarketBarMinuteModel,
)
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.watchlist import WatchlistItemModel


def user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        last_login_at=model.last_login_at,
    )


def user_to_credentials(model: UserModel) -> UserCredentials:
    return UserCredentials(
        id=model.id,
        email=model.email,
        email_normalized=model.email_normalized,
        password_hash=model.password_hash,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        last_login_at=model.last_login_at,
    )


def watchlist_item_to_domain(model: WatchlistItemModel) -> WatchlistItem:
    return WatchlistItem(ticker=model.ticker, created_at=model.created_at)


def market_bar_day_to_domain(model: MarketBarDayModel) -> MarketBar:
    return MarketBar(
        ticker=model.ticker,
        timespan="day",
        multiplier=1,
        start_at=model.start_at,
        open=model.open,
        high=model.high,
        low=model.low,
        close=model.close,
        volume=model.volume,
        vwap=model.vwap,
        trades=model.trades,
        source=model.source,
    )


def market_bar_minute_to_domain(model: MarketBarMinuteModel) -> MarketBar:
    return MarketBar(
        ticker=model.ticker,
        timespan="minute",
        multiplier=1,
        start_at=model.start_at,
        open=model.open,
        high=model.high,
        low=model.low,
        close=model.close,
        volume=model.volume,
        vwap=model.vwap,
        trades=model.trades,
        source=model.source,
    )


def market_bar_minute_agg_to_domain(model: MarketBarMinuteAggModel) -> MarketBar:
    return MarketBar(
        ticker=model.ticker,
        timespan="minute",
        multiplier=model.multiplier,
        start_at=model.bucket_start_at,
        end_at=model.bucket_end_at,
        open=model.open,
        high=model.high,
        low=model.low,
        close=model.close,
        volume=model.volume,
        vwap=model.vwap,
        trades=model.trades,
        source=model.source,
        is_final=model.is_final,
    )


def market_bar_to_day_row(bar: MarketBar, *, trade_date: date) -> dict:
    return {
        "ticker": bar.ticker,
        "trade_date": trade_date,
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


def market_bar_to_minute_row(bar: MarketBar, *, trade_date: date) -> dict:
    return {
        "ticker": bar.ticker,
        "trade_date": trade_date,
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


def market_bar_to_minute_agg_row(bar: MarketBar, *, trade_date: date) -> dict:
    bucket_end_at = bar.end_at
    if bucket_end_at is None:
        raise ValueError("Aggregated market bar requires end_at")
    if bar.multiplier <= 1:
        raise ValueError("Aggregated market bar requires multiplier > 1")

    return {
        "ticker": bar.ticker,
        "trade_date": trade_date,
        "multiplier": bar.multiplier,
        "bucket_start_at": bar.start_at,
        "bucket_end_at": bucket_end_at,
        "is_final": bar.is_final if bar.is_final is not None else True,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "vwap": bar.vwap,
        "trades": bar.trades,
        "source": bar.source,
    }
