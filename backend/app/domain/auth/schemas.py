from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class User(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class UserCredentials(User):
    email_normalized: str
    password_hash: str


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
