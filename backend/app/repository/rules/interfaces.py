from __future__ import annotations

from typing import Protocol


class RulesRepository(Protocol):
    def list_rules(self) -> list[dict]: ...

    def create_rule(self, *, data: dict) -> dict: ...
