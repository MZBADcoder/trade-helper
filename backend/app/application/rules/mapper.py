from __future__ import annotations

from app.api.dto.rules import RuleCreate, RuleOut
from app.domain.rules.schemas import Rule, RuleIn


def to_domain_create(dto: RuleCreate) -> RuleIn:
    return RuleIn(**dto.model_dump())


def to_domain_rule(dto: RuleOut) -> Rule:
    return Rule(**dto.model_dump())


def to_dto(rule: Rule) -> RuleOut:
    return RuleOut(**rule.model_dump())
