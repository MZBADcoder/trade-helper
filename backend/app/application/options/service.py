from __future__ import annotations

from app.domain.options.schemas import OptionChainResult, OptionContract, OptionExpirationsResult


class DefaultOptionsApplicationService:
    def list_expirations(
        self,
        *,
        underlying: str,
        limit: int = 12,
        include_expired: bool = False,
    ) -> OptionExpirationsResult:
        _ = (underlying, limit, include_expired)
        raise ValueError("OPTIONS_UPSTREAM_UNAVAILABLE")

    def list_chain(
        self,
        *,
        underlying: str,
        expiration: str,
        strike_from: float | None = None,
        strike_to: float | None = None,
        option_type: str = "all",
        limit: int = 200,
        cursor: str | None = None,
    ) -> OptionChainResult:
        _ = (underlying, expiration, strike_from, strike_to, option_type, limit, cursor)
        raise ValueError("OPTIONS_UPSTREAM_UNAVAILABLE")

    def get_contract(
        self,
        *,
        option_ticker: str,
        include_greeks: bool = True,
    ) -> OptionContract:
        _ = (option_ticker, include_greeks)
        raise ValueError("OPTIONS_UPSTREAM_UNAVAILABLE")
