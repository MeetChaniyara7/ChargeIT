"""Request and response shapes for login, registration and the current user."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoogleLoginRequest(BaseModel):
    credential: str


class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    full_name: str | None = None
    phone: str | None = None
    google_user_id: str | None = None
    role: str = "USER"
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
