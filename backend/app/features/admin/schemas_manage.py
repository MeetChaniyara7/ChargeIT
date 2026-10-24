"""Admin shapes for managing people and money: users and roles, operators, payments, and the activity log."""

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Role = Literal["USER", "ADMIN"]


# ---------------------------------------------------------------- users and roles

class UserRow(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None = None
    role: str
    sign_in: str  # how they sign in: GOOGLE, PASSWORD or BOTH
    bookings: int
    created_at: dt.datetime | None = None
    is_you: bool = False


class UserRows(BaseModel):
    items: list[UserRow]
    total: int
    page: int
    page_size: int
    admins: int  # how many admins there are right now


class RoleChange(BaseModel):
    role: Role


# ---------------------------------------------------------------- operators

class OperatorRow(BaseModel):
    operator_id: UUID
    name: str
    website: str | None = None
    station_count: int


class OperatorIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    website: str | None = Field(default=None, max_length=300)


class OperatorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    website: str | None = Field(default=None, max_length=300)


# ---------------------------------------------------------------- payments

class PaymentRow(BaseModel):
    payment_id: UUID
    purpose: str  # BOOKING_FEE, ENERGY or WALKIN_PREPAID
    status: str
    amount: float
    refunded_amount: float
    provider_payment_id: str | None = None
    station_name: str | None = None
    user_email: str | None = None
    created_at: dt.datetime


class PaymentRows(BaseModel):
    items: list[PaymentRow]
    total: int
    page: int
    page_size: int
    amount_total: float  # of everything that matches the filters (not just this page)
    refunded_total: float


# ---------------------------------------------------------------- kiosks

class DeviceRename(BaseModel):
    name: str = Field(min_length=1, max_length=60)


# ---------------------------------------------------------------- activity log

class ActivityRow(BaseModel):
    action_id: int
    admin_email: str
    action: str
    target: str | None = None
    details: dict
    created_at: dt.datetime


class ActivityRows(BaseModel):
    items: list[ActivityRow]
    total: int
    page: int
    page_size: int
