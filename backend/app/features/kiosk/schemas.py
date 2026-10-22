"""What the kiosk sends and receives. Nothing here ever names a person, a phone number or an app user's bill."""

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WalkInOption(BaseModel):
    """One choice on the "how much?" screen. The kWh figure is worked out on the server."""

    kind: Literal["AMOUNT", "UNTIL_NEXT"]
    amount: int
    kwh: float
    until: dt.datetime | None = None  # UNTIL_NEXT: when charging will stop


class WalkInProgress(BaseModel):
    """A walk-in session in progress: how much of the prepaid amount is used."""

    prepaid: float
    used: float


class WalkInDone(BaseModel):
    """A walk-in that just finished (shown on the tile for two minutes)."""

    used: float
    refunded: float
    ended_at: dt.datetime


class ChargerTile(BaseModel):
    charger_id: UUID
    label: str
    connector_type: str
    power_kw: float | None = None
    price_per_kwh: float | None = None
    state: Literal["FREE", "RESERVED", "CHARGING", "PAYING", "OUT_OF_SERVICE"]
    free_until: dt.datetime | None = None  # FREE: the next booking needs it from here (None = no booking in sight)
    reserved_for: dt.datetime | None = None  # RESERVED: start of the booking it is kept for
    ends_at: dt.datetime | None = None  # CHARGING: when it will stop by itself (None = unknown)
    progress_percent: float | None = None  # CHARGING: battery level, if known
    walk_in: WalkInProgress | None = None
    last_walk_in: WalkInDone | None = None
    can_walk_in: bool = False
    walk_in_blocked_reason: str | None = None
    options: list[WalkInOption] = []


class KioskStatus(BaseModel):
    station_name: str
    server_time: dt.datetime
    idle_reset_seconds: int
    chargers: list[ChargerTile]


class OtpStartRequest(BaseModel):
    otp: str = Field(min_length=1, max_length=12)


class OtpStartOut(BaseModel):
    charger_id: UUID
    charger_label: str
    connector_type: str
    session_id: UUID


class WalkInCreate(BaseModel):
    charger_id: UUID
    amount: int | None = Field(default=None, gt=0, description="One of the offered amounts, in rupees.")
    until_next: bool = False


class WalkInOut(BaseModel):
    walk_in_id: UUID
    status: Literal["WAITING_FOR_PAYMENT", "PAID", "EXPIRED", "CANCELLED"]
    charger_id: UUID
    charger_label: str
    amount: float
    payment_url: str | None = None  # shown as a QR code while WAITING_FOR_PAYMENT
    expires_at: dt.datetime
    server_time: dt.datetime
    seconds_left: int
    session_id: UUID | None = None  # once PAID
    refunded: float = 0  # a payment that arrived too late is refunded in full (recorded; no money moves in test mode)


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="A label for the tablet, e.g. 'Entrance kiosk'.")


class DeviceOut(BaseModel):
    device_id: UUID
    station_id: UUID
    name: str
    key_prefix: str
    is_active: bool
    last_seen_at: dt.datetime | None = None
    created_at: dt.datetime


class DeviceCreated(DeviceOut):
    key: str  # shown this once; only its hash is stored
