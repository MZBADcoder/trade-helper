from __future__ import annotations


class MarketDataApplicationError(ValueError):
    """Base error for market data application layer."""


class MarketDataRangeTooLargeError(MarketDataApplicationError):
    """Raised when requested bars range exceeds service policy."""

    def __init__(self) -> None:
        super().__init__("MARKET_DATA_RANGE_TOO_LARGE")


class MarketDataRateLimitedError(MarketDataApplicationError):
    """Raised when upstream market data provider rate limits request."""

    def __init__(self) -> None:
        super().__init__("MARKET_DATA_RATE_LIMITED")


class MarketDataUpstreamUnavailableError(MarketDataApplicationError):
    """Raised when upstream market data provider is unavailable."""

    def __init__(self) -> None:
        super().__init__("MARKET_DATA_UPSTREAM_UNAVAILABLE")
