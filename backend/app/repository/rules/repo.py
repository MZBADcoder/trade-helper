from __future__ import annotations

from app.repository.rules.interfaces import RulesRepository


class SqlAlchemyRulesRepository(RulesRepository):
    def __init__(self, *, session: object | None = None) -> None:
        self._session = session

    def list_rules(self) -> list[dict]:
        raise NotImplementedError("rules repository not implemented")

    def create_rule(self, *, data: dict) -> dict:
        raise NotImplementedError("rules repository not implemented")
