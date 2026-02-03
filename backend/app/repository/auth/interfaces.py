from __future__ import annotations

from typing import Protocol

from app.domain.auth.schemas import User, UserCredentials


class AuthRepository(Protocol):
    def create_user(
        self,
        *,
        email: str,
        email_normalized: str,
        password_hash: str,
    ) -> User: ...

    def get_user_by_email_normalized(self, *, email_normalized: str) -> UserCredentials | None: ...

    def get_user_by_id(self, *, user_id: int) -> User | None: ...

    def update_last_login(self, *, user_id: int) -> User | None: ...
