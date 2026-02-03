from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_market_data_service
from app.api.v1.dto.market_data import MarketBarOut
from app.application.market_data.service import DefaultMarketDataApplicationService
from app.domain.auth.schemas import User
from app.domain.market_data.schemas import MarketBar

router = APIRouter()


def _to_dto(bar: MarketBar) -> MarketBarOut:
    return MarketBarOut(**bar.model_dump(exclude={"source"}))


@router.get("/bars", response_model=list[MarketBarOut])
def list_bars(
    ticker: str,
    timespan: str = "day",
    multiplier: int = 1,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    limit: int | None = Query(None, ge=1, le=50000),
    service: DefaultMarketDataApplicationService = Depends(get_market_data_service),
    current_user: User = Depends(get_current_user),
) -> list[MarketBarOut]:
    _ = current_user
    try:
        bars = service.list_bars(
            ticker=ticker,
            timespan=timespan,
            multiplier=multiplier,
            start_date=from_date,
            end_date=to_date,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_to_dto(bar) for bar in bars]
