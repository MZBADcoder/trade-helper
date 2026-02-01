from __future__ import annotations

from fastapi import APIRouter

from app.api.dto.rules import RuleCreate, RuleOut

router = APIRouter()


@router.get("", response_model=list[RuleOut])
def list_rules() -> list[RuleOut]:
    return []


@router.post("", response_model=RuleOut)
def create_rule(payload: RuleCreate) -> RuleOut:
    return RuleOut(id=0, key=payload.key, name=payload.name)
