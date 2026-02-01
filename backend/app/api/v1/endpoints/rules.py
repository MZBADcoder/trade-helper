from fastapi import APIRouter

from app.application.rules.service import DefaultRulesApplicationService
from app.api.dto.rules import RuleCreate, RuleOut

router = APIRouter()


@router.get("", response_model=list[RuleOut])
def list_rules() -> list[RuleOut]:
    service = DefaultRulesApplicationService()
    rules = service.list_rules()
    return [RuleOut(**rule) for rule in rules]


@router.post("", response_model=RuleOut)
def create_rule(payload: RuleCreate) -> RuleOut:
    service = DefaultRulesApplicationService()
    rule = service.create_rule(data=payload.model_dump())
    return RuleOut(**rule)
