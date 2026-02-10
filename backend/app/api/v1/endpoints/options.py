from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_options_service
from app.api.errors import raise_api_error
from app.api.v1.dto.mappers import to_option_chain_out, to_option_contract_out, to_option_expirations_out
from app.api.v1.dto.options import OptionChainOut, OptionContractOut, OptionExpirationsOut
from app.application.options.service import DefaultOptionsApplicationService
from app.domain.auth.schemas import User

router = APIRouter()
_UNDERLYING_PATTERN = r"^[A-Z.]{1,15}$"


@router.get("/expirations", response_model=OptionExpirationsOut)
def list_expirations(
    underlying: str,
    limit: int = 12,
    include_expired: bool = False,
    service: DefaultOptionsApplicationService = Depends(get_options_service),
    current_user: User = Depends(get_current_user),
) -> OptionExpirationsOut:
    _ = current_user
    normalized = _normalize_underlying(underlying)
    if limit < 1 or limit > 36:
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_LIMIT",
            message="limit must be between 1 and 36",
        )

    try:
        result = service.list_expirations(
            underlying=normalized,
            limit=limit,
            include_expired=include_expired,
        )
        return to_option_expirations_out(result)
    except ValueError as exc:
        _raise_options_service_error(exc)


@router.get("/chain", response_model=OptionChainOut)
def list_chain(
    underlying: str,
    expiration: str,
    strike_from: float | None = None,
    strike_to: float | None = None,
    option_type: str = "all",
    limit: int = 200,
    cursor: str | None = None,
    service: DefaultOptionsApplicationService = Depends(get_options_service),
    current_user: User = Depends(get_current_user),
) -> OptionChainOut:
    _ = current_user
    normalized = _normalize_underlying(underlying)
    _validate_expiration(expiration)
    if strike_from is not None and strike_to is not None and strike_from > strike_to:
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_STRIKE_RANGE",
            message="strike_from must be <= strike_to",
        )
    normalized_type = option_type.strip().lower()
    if normalized_type not in {"call", "put", "all"}:
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_OPTION_TYPE",
            message="option_type must be call, put, or all",
        )
    if limit < 1 or limit > 500:
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_LIMIT",
            message="limit must be between 1 and 500",
        )

    try:
        result = service.list_chain(
            underlying=normalized,
            expiration=expiration,
            strike_from=strike_from,
            strike_to=strike_to,
            option_type=normalized_type,
            limit=limit,
            cursor=cursor,
        )
        return to_option_chain_out(result)
    except ValueError as exc:
        _raise_options_service_error(exc)


@router.get("/contracts/{option_ticker}", response_model=OptionContractOut)
def get_contract(
    option_ticker: str,
    include_greeks: bool = Query(True),
    service: DefaultOptionsApplicationService = Depends(get_options_service),
    current_user: User = Depends(get_current_user),
) -> OptionContractOut:
    _ = current_user
    normalized_ticker = option_ticker.strip().upper()
    if not normalized_ticker.startswith("O:"):
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_TICKER",
            message="option_ticker must start with O:",
        )

    try:
        result = service.get_contract(
            option_ticker=normalized_ticker,
            include_greeks=include_greeks,
        )
        return to_option_contract_out(result)
    except ValueError as exc:
        _raise_options_service_error(exc)


def _normalize_underlying(underlying: str) -> str:
    symbol = underlying.strip().upper()
    if not symbol:
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_UNDERLYING",
            message="underlying is required",
        )
    if not _matches_underlying(symbol):
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_UNDERLYING",
            message="underlying has invalid format",
        )
    return symbol


def _matches_underlying(symbol: str) -> bool:
    return bool(re.fullmatch(_UNDERLYING_PATTERN, symbol))


def _validate_expiration(expiration: str) -> None:
    try:
        date.fromisoformat(expiration)
    except ValueError:
        raise_api_error(
            status_code=400,
            code="OPTIONS_INVALID_EXPIRATION",
            message="expiration must be YYYY-MM-DD",
        )


def _raise_options_service_error(exc: ValueError) -> None:
    detail = str(exc)
    if detail in {"OPTIONS_UNDERLYING_NOT_FOUND", "OPTIONS_CHAIN_NOT_FOUND", "OPTIONS_CONTRACT_NOT_FOUND"}:
        raise_api_error(
            status_code=404,
            code=detail,
            message=detail.lower().replace("_", " "),
        )
    if detail == "OPTIONS_UPSTREAM_UNAVAILABLE":
        raise_api_error(
            status_code=502,
            code=detail,
            message="options upstream unavailable",
        )
    raise_api_error(
        status_code=400,
        code=detail if detail.startswith("OPTIONS_") else "OPTIONS_INVALID_REQUEST",
        message=detail,
    )
