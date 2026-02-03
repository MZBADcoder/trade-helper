from __future__ import annotations

from typing import Protocol

from app.domain.auth.schemas import User


class AuthService(Protocol):
    def register(self, *, email: str, password: str) -> User: ...

    def authenticate(self, *, email: str, password: str) -> User: ...

    def get_user(self, *, user_id: int) -> User | None: ...
