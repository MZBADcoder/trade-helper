from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
