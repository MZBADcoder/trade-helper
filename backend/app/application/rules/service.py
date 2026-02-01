from __future__ import annotations

from app.application.rules.interfaces import RulesApplicationService
from app.domain.rules.interfaces import RulesService


class DefaultRulesApplicationService(RulesApplicationService):
    def __init__(self, *, service: RulesService | None = None) -> None:
        self._service = service

    def list_rules(self) -> list[dict]:
        raise NotImplementedError("rules application service not implemented")

    def create_rule(self, *, data: dict) -> dict:
        raise NotImplementedError("rules application service not implemented")
