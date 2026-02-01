from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.dto.alerts import AlertOut

router = APIRouter()


@router.get("", response_model=list[AlertOut])
def list_alerts(limit: int = Query(50, ge=1, le=200)) -> list[AlertOut]:
    _ = limit
    return []
