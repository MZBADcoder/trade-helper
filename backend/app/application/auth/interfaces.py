from __future__ import annotations

from typing import Protocol

from app.domain.auth.schemas import AccessToken, User


class AuthApplicationService(Protocol):
    def register(self, *, email: str, password: str) -> User: ...

    def login(self, *, email: str, password: str) -> AccessToken: ...

    def get_user(self, *, user_id: int) -> User | None: ...

    def get_current_user_from_token(self, *, token: str) -> User: ...
