"""Request and response shapes for bookings."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    charger_id: UUID
    start: datetime = Field(description="When the slot starts: on a :00 or :30 boundary, in the future, within 7 days")
    blocks: int = Field(ge=1, le=4, description="How many 30-minute blocks (1-4)")
    vehicle_id: UUID | None = None


class InstantCreate(BaseModel):
    charger_id: UUID
    vehicle_id: UUID | None = None


class BookingStation(BaseModel):
    station_id: UUID
    name: str
    address: str
    city: str | None = None
    latitude: float
    longitude: float


class BookingCharger(BaseModel):
    charger_id: UUID
    label: str
    connector_type: str
    power_kw: float | None = None
    price_per_kwh: float | None = None


class BookingOut(BaseModel):
    booking_id: UUID
    # The truth as of now: a hold whose time ran out reads EXPIRED even before the background job marks it.
    status: str
    source: str
    start: datetime
    end: datetime
    blocks: int
    hold_expires_at: datetime | None = None
    # The server's clock when this was sent. The hold countdown uses hold_expires_at minus this,
    # so a phone with the wrong time still shows the right number of seconds.
    server_time: datetime
    booking_fee: float
    fee_paid: bool
    refund_amount: float
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    created_at: datetime | None = None
    station: BookingStation
    charger: BookingCharger
    # When the one-time code works at the kiosk.
    code_valid_from: datetime
    code_valid_until: datetime
    has_code: bool
    code_used: bool
    can_cancel: bool
    can_show_new_code: bool
    # Set when the charger's situation changed this booking: it was moved to another charger, the driver
    # was warned the charger may be busy, or it was cancelled because no charger was free (fee refunded).
    notice_kind: str | None = None  # WARNING | MOVED | CANCELLED_NO_CHARGER
    notice_text: str | None = None
    # The live charging page of this booking, once charging has started.
    session_id: UUID | None = None


class InstantBookingOut(BookingOut):
    """Returned once when a "Charge now" booking is created: the code is never shown again."""

    otp: str


class OtpOut(BaseModel):
    booking_id: UUID
    otp: str
    valid_from: datetime
    valid_until: datetime
    note: str = "This code is shown once. Showing a new code makes this one stop working."


class RefundPreview(BaseModel):
    booking_id: UUID
    fee_paid: float
    refund_amount: float
    percent: int
    reason: str


class SlotAlternative(BaseModel):
    start: datetime
    end: datetime


class ChargerAlternative(BaseModel):
    charger_id: UUID
    label: str
    connector_type: str
    power_kw: float | None = None
    price_per_kwh: float | None = None
    start: datetime
    end: datetime


class StationAlternative(BaseModel):
    station_id: UUID
    name: str
    distance_km: float
    travel_minutes: float
    reason: str
    start: datetime
    end: datetime
    charger_id: UUID | None = None


class Alternatives(BaseModel):
    """What to offer when a slot was just taken. Each entry can be booked in one tap."""

    charger_id: UUID
    blocks: int
    same_charger: list[SlotAlternative]
    other_chargers: list[ChargerAlternative]
    stations: list[StationAlternative]


class DueItem(BaseModel):
    session_id: UUID
    booking_id: UUID | None = None
    station_name: str | None = None
    amount: float
    ended_at: datetime | None = None


class DuesOut(BaseModel):
    count: int
    total: float
    items: list[DueItem]


class SlotTakenDetails(BaseModel):
    alternatives: Alternatives


class SlotTakenError(BaseModel):
    code: str = Field(examples=["SLOT_TAKEN"])
    message: str
    details: SlotTakenDetails


class SlotTakenResponse(BaseModel):
    """The body of the 409 answer when someone else got the slot first. Documents the error for the generated API types."""

    error: SlotTakenError
