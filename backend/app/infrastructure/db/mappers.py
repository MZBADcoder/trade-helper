from __future__ import annotations

from app.domain.auth.schemas import User, UserCredentials
from app.domain.market_data.schemas import MarketBar
from app.domain.watchlist.schemas import WatchlistItem
from app.infrastructure.db.models.market_data import MarketBarModel
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


def market_bar_to_domain(model: MarketBarModel) -> MarketBar:
    return MarketBar(
        ticker=model.ticker,
        timespan=model.timespan,
        multiplier=model.multiplier,
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


def market_bar_to_row(bar: MarketBar) -> dict:
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
