from __future__ import annotations

from app.api.v1.dto.auth import AccessTokenOut, UserOut
from app.api.v1.dto.market_data import MarketBarOut
from app.api.v1.dto.watchlist import WatchlistItemDeletedOut, WatchlistItemOut
from app.domain.auth.schemas import AccessToken, User
from app.domain.market_data.schemas import MarketBar
from app.domain.watchlist.schemas import WatchlistItem


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


def to_access_token_out(token: AccessToken) -> AccessTokenOut:
    return AccessTokenOut(
        access_token=token.access_token,
        token_type=token.token_type,
        expires_in=token.expires_in,
    )


def to_watchlist_item_out(item: WatchlistItem) -> WatchlistItemOut:
    return WatchlistItemOut(
        ticker=item.ticker,
        created_at=item.created_at,
    )


def to_watchlist_item_deleted_out(ticker: str) -> WatchlistItemDeletedOut:
    return WatchlistItemDeletedOut(deleted=ticker.upper())


def to_market_bar_out(bar: MarketBar) -> MarketBarOut:
    return MarketBarOut(
        ticker=bar.ticker,
        timespan=bar.timespan,
        multiplier=bar.multiplier,
        start_at=bar.start_at,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        vwap=bar.vwap,
        trades=bar.trades,
    )
