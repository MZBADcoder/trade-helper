from __future__ import annotations

import pytest

from app.application.options.service import DefaultOptionsApplicationService


def test_list_expirations_raises_options_upstream_unavailable_until_implemented() -> None:
    service = DefaultOptionsApplicationService()

    with pytest.raises(ValueError, match="OPTIONS_UPSTREAM_UNAVAILABLE"):
        service.list_expirations(underlying="AAPL")


def test_list_chain_raises_options_upstream_unavailable_until_implemented() -> None:
    service = DefaultOptionsApplicationService()

    with pytest.raises(ValueError, match="OPTIONS_UPSTREAM_UNAVAILABLE"):
        service.list_chain(
            underlying="AAPL",
            expiration="2026-02-21",
        )


def test_get_contract_raises_options_upstream_unavailable_until_implemented() -> None:
    service = DefaultOptionsApplicationService()

    with pytest.raises(ValueError, match="OPTIONS_UPSTREAM_UNAVAILABLE"):
        service.get_contract(option_ticker="O:AAPL260221C00210000")
