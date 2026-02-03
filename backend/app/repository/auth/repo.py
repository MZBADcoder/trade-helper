from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.auth.constants import ERROR_EMAIL_ALREADY_REGISTERED
from app.domain.auth.schemas import User, UserCredentials
from app.infrastructure.db.models.user import UserModel


class SqlAlchemyAuthRepository:
    def __init__(self, *, session: object | None = None) -> None:
        if session is None:
            raise ValueError("session is required")
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
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(ERROR_EMAIL_ALREADY_REGISTERED) from exc
        self._session.refresh(user)
        return self._to_user(user)

    def get_user_by_email_normalized(self, *, email_normalized: str) -> UserCredentials | None:
        stmt = select(UserModel).where(UserModel.email_normalized == email_normalized)
        user = self._session.execute(stmt).scalar_one_or_none()
        if user is None:
            return None
        return self._to_user_credentials(user)

    def get_user_by_id(self, *, user_id: int) -> User | None:
        user = self._session.get(UserModel, user_id)
        if user is None:
            return None
        return self._to_user(user)

    def update_last_login(self, *, user_id: int) -> User | None:
        user = self._session.get(UserModel, user_id)
        if user is None:
            return None
        user.last_login_at = datetime.now(tz=timezone.utc)
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return self._to_user(user)

    @staticmethod
    def _to_user(item: UserModel) -> User:
        return User(
            id=item.id,
            email=item.email,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
            last_login_at=item.last_login_at,
        )

    @staticmethod
    def _to_user_credentials(item: UserModel) -> UserCredentials:
        return UserCredentials(
            id=item.id,
            email=item.email,
            email_normalized=item.email_normalized,
            password_hash=item.password_hash,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
            last_login_at=item.last_login_at,
        )
