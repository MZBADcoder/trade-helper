from __future__ import annotations

from app.repository.rules.interfaces import RulesRepository
from app.domain.rules.interfaces import RulesService


class DefaultRulesService(RulesService):
    def __init__(self, *, repository: RulesRepository | None = None) -> None:
        self._repository = repository

    def list_rules(self) -> list[dict]:
        raise NotImplementedError("rules service not implemented")

    def create_rule(self, *, data: dict) -> dict:
        raise NotImplementedError("rules service not implemented")
