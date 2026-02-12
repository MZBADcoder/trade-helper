from __future__ import annotations

from app.api.v1.dto.auth import AccessTokenOut, UserOut
from app.api.v1.dto.market_data import MarketBarOut, MarketSnapshotOut
from app.api.v1.dto.options import OptionChainOut, OptionContractOut, OptionExpirationsOut
from app.api.v1.dto.watchlist import WatchlistItemDeletedOut, WatchlistItemOut
from app.domain.auth.schemas import AccessToken, User
from app.domain.market_data.schemas import MarketBar, MarketSnapshot
from app.domain.options.schemas import OptionChainResult, OptionContract, OptionExpirationsResult
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


def to_market_snapshot_out(snapshot: MarketSnapshot) -> MarketSnapshotOut:
    return MarketSnapshotOut(
        ticker=snapshot.ticker,
        last=snapshot.last,
        change=snapshot.change,
        change_pct=snapshot.change_pct,
        open=snapshot.open,
        high=snapshot.high,
        low=snapshot.low,
        volume=snapshot.volume,
        updated_at=snapshot.updated_at,
        market_status=snapshot.market_status,
        source=snapshot.source,
    )


def to_option_expirations_out(result: OptionExpirationsResult) -> OptionExpirationsOut:
    return OptionExpirationsOut(
        underlying=result.underlying,
        expirations=result.expirations,
        source=result.source,
        updated_at=result.updated_at,
    )


def to_option_chain_out(result: OptionChainResult) -> OptionChainOut:
    return OptionChainOut(
        underlying=result.underlying,
        expiration=result.expiration,
        items=result.items,
        next_cursor=result.next_cursor,
    )


def to_option_contract_out(contract: OptionContract) -> OptionContractOut:
    return OptionContractOut(
        option_ticker=contract.option_ticker,
        underlying=contract.underlying,
        expiration=contract.expiration,
        option_type=contract.option_type,
        strike=contract.strike,
        multiplier=contract.multiplier,
        quote=contract.quote,
        session=contract.session,
        greeks=contract.greeks,
        source=contract.source,
    )
