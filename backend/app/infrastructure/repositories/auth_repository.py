from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.auth.constants import ERROR_EMAIL_ALREADY_REGISTERED
from app.domain.auth.schemas import User, UserCredentials
from app.infrastructure.db.mappers import user_to_credentials, user_to_domain
from app.infrastructure.db.models.user import UserModel


class SqlAlchemyAuthRepository:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def create_user(
        self,
        *,
        email: str,
        email_normalized: str,
        password_hash: str,
    ) -> User:
        user = UserModel(
            email=email,
            email_normalized=email_normalized,
            password_hash=password_hash,
            is_active=True,
        )
        self._session.add(user)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(ERROR_EMAIL_ALREADY_REGISTERED) from exc
        return user_to_domain(user)

    def get_user_by_email_normalized(self, *, email_normalized: str) -> UserCredentials | None:
        stmt = select(UserModel).where(UserModel.email_normalized == email_normalized)
        user = self._session.execute(stmt).scalar_one_or_none()
        if user is None:
            return None
        return user_to_credentials(user)

    def get_user_by_id(self, *, user_id: int) -> User | None:
        user = self._session.get(UserModel, user_id)
        if user is None:
            return None
        return user_to_domain(user)

    def update_last_login(self, *, user_id: int) -> User | None:
        user = self._session.get(UserModel, user_id)
        if user is None:
            return None
        user.last_login_at = datetime.now(tz=timezone.utc)
        self._session.add(user)
        self._session.flush()
        return user_to_domain(user)
