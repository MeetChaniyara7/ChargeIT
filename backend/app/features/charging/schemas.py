"""What the live charging page shows. Everything is worked out on the server."""

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.features.bookings.schemas import BookingCharger, BookingStation


class LiveSession(BaseModel):
    session_id: UUID
    booking_id: UUID | None = None
    status: Literal["RUNNING", "ENDED"]
    source: str  # BOOKING | WALK_IN | EXTERNAL
    station: BookingStation
    charger: BookingCharger
    started_at: dt.datetime
    # When it will stop by itself (the end of the booked slot). The server's clock is sent too, so the
    # page can count down without trusting the phone's clock.
    planned_stop_at: dt.datetime | None = None
    server_time: dt.datetime
    seconds_left: int | None = None
    # Energy delivered so far (or in total once ended), the battery level, and the cost so far.
    energy_kwh: float
    battery_percent: float
    cost_so_far: float
    ended_at: dt.datetime | None = None
    end_reason: str | None = None
    duration_minutes: float
    # Once ended: the bill and whether it has been paid.
    bill_amount: float | None = None
    bill_status: str | None = None
    # The page warns about an automatic stop this long before it (stop_warning is true inside it).
    stop_warning: bool = False
    next_booking_waiting: bool = False
    can_stop: bool = False


class StopResult(LiveSession):
    """The session after the driver stopped it (the same shape, now ENDED)."""


class StartedSession(BaseModel):
    session_id: UUID
    booking_id: UUID
    charger_id: UUID
