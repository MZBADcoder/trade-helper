from fastapi import APIRouter

from app.db.session import db
from app.schemas.rules import RuleCreate, RuleOut

router = APIRouter()


@router.get("", response_model=list[RuleOut])
def list_rules() -> list[RuleOut]:
    rules = db.rules_list()
    return [RuleOut(**rule) for rule in rules]


@router.post("", response_model=RuleOut)
def create_rule(payload: RuleCreate) -> RuleOut:
    rule = db.rules_create(payload.model_dump())
    return RuleOut(**rule)

