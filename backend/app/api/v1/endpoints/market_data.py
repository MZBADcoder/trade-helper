from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dto.market_data import MarketBarOut
from app.application.market_data.service import DefaultMarketDataApplicationService
from app.core.config import settings
from app.domain.market_data.schemas import MarketBar
from app.infrastructure.clients.polygon import PolygonClient
from app.infrastructure.db.session import get_db
from app.repository.market_data.repo import SqlAlchemyMarketDataRepository

router = APIRouter()


def _to_dto(bar: MarketBar) -> MarketBarOut:
    return MarketBarOut(**bar.model_dump(exclude={"source"}))


def _build_service(db: Session) -> DefaultMarketDataApplicationService:
    repository = SqlAlchemyMarketDataRepository(session=db)
    polygon_client = PolygonClient(settings.polygon_api_key) if settings.polygon_api_key else None
    return DefaultMarketDataApplicationService(repository=repository, polygon_client=polygon_client)


@router.get("/bars", response_model=list[MarketBarOut])
def list_bars(
    ticker: str,
    timespan: str = "day",
    multiplier: int = 1,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    limit: int | None = Query(None, ge=1, le=50000),
    db: Session = Depends(get_db),
) -> list[MarketBarOut]:
    service = _build_service(db)
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
