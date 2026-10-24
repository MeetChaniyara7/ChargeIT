"""What the admin pages send and receive. Admins may see more than drivers (an email on a booking, for example)."""

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.stations.schemas import ConnectorType

CurrentType = Literal["AC", "DC"]


# ---------------------------------------------------------------- overview and reports

class DayCount(BaseModel):
    day: dt.date  # an India-time (IST) calendar day
    count: int


class StationCount(BaseModel):
    station_name: str
    count: int


class Revenue(BaseModel):
    booking_fees: float
    energy: float
    walk_ins: float
    refunds: float  # money recorded as refunded (not part of the three above, which are net of refunds)


class OverviewOut(BaseModel):
    today_bookings: int
    active_sessions: int
    no_shows_week: int
    open_alerts: int
    revenue: Revenue  # last 30 days
    revenue_days: int
    bookings_per_day: list[DayCount]  # last 14 days
    no_shows_by_station: list[StationCount]  # last 30 days, the worst few


class StatusCount(BaseModel):
    status: str
    count: int


class SettlementRow(BaseModel):
    operator_name: str
    sessions: int
    energy_revenue: float  # energy bills paid + walk-in sessions, net of refunds


class ReportOut(BaseModel):
    date_from: dt.date
    date_to: dt.date
    bookings_by_status: list[StatusCount]
    no_shows: int
    revenue: Revenue
    settlement: list[SettlementRow]


# ---------------------------------------------------------------- stations and chargers

class StationRow(BaseModel):
    station_id: UUID
    name: str
    city: str | None = None
    operator_name: str | None = None
    data_source: str
    is_active: bool
    charger_count: int
    has_estimated_data: bool


class StationRows(BaseModel):
    items: list[StationRow]
    total: int
    page: int
    page_size: int


class AdminCharger(BaseModel):
    charger_id: UUID
    label: str
    connector_type: str
    current_type: str | None = None
    power_kw: float | None = None
    price_per_kwh: float | None = None
    status: str
    data_source: str


class AdminStation(BaseModel):
    station_id: UUID
    name: str
    address: str
    city: str | None = None
    latitude: float
    longitude: float
    operator_id: UUID | None = None
    operator_name: str | None = None
    opening_hours: str | None = None
    is_active: bool
    data_source: str
    has_estimated_data: bool
    chargers: list[AdminCharger]


class StationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    operator_id: UUID | None = None
    opening_hours: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None
    # Needed to deactivate a station that still has future bookings: they are cancelled with a full refund.
    cancel_bookings: bool = False


class ChargerCreate(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    connector_type: ConnectorType
    current_type: CurrentType | None = None
    power_kw: float | None = Field(default=None, gt=0, le=1000)
    price_per_kwh: float | None = Field(default=None, ge=0, le=1000)


class ChargerUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=40)
    connector_type: ConnectorType | None = None
    current_type: CurrentType | None = None
    power_kw: float | None = Field(default=None, gt=0, le=1000)
    price_per_kwh: float | None = Field(default=None, ge=0, le=1000)


class AffectedBooking(BaseModel):
    booking_id: UUID
    status: str
    source: str
    start: dt.datetime
    end: dt.datetime
    user_email: str | None = None
    fee_paid: float


class AffectedOut(BaseModel):
    charger_id: UUID
    label: str
    charging_now: bool  # a session is running: it will be ended and billed
    bookings: list[AffectedBooking]


class OutOfServiceRequest(BaseModel):
    cancel_bookings: bool = False


class OutOfServiceResult(BaseModel):
    status: str
    cancelled: int
    refunded_total: float
    session_ended: bool


class ChargerEventOut(BaseModel):
    event_id: int
    event: str
    source: str
    details: dict
    created_at: dt.datetime


# ---------------------------------------------------------------- bookings

class BookingRow(BaseModel):
    booking_id: UUID
    status: str
    source: str
    start: dt.datetime
    end: dt.datetime
    station_name: str
    charger_label: str
    user_email: str | None = None
    booking_fee: float
    refund_amount: float
    created_at: dt.datetime


class BookingRows(BaseModel):
    items: list[BookingRow]
    total: int
    page: int
    page_size: int


class BookingEventOut(BaseModel):
    event_id: int
    from_status: str | None = None
    to_status: str
    actor: str
    reason: str | None = None
    created_at: dt.datetime


# ---------------------------------------------------------------- kiosks and alerts

class DeviceRow(BaseModel):
    device_id: UUID
    station_id: UUID
    station_name: str
    name: str
    key_prefix: str
    is_active: bool
    last_seen_at: dt.datetime | None = None
    created_at: dt.datetime


class AlertOut(BaseModel):
    alert_id: UUID
    kind: str
    station_name: str | None = None
    message: str
    details: dict
    created_at: dt.datetime
    resolved_at: dt.datetime | None = None
