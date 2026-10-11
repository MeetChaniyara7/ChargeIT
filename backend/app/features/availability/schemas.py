"""The shape of the availability grid."""

import datetime as dt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

# FREE         nobody has it and it can be booked
# BOOKED       a confirmed or active booking holds it
# HELD         someone is paying for it right now (frees up if they don't finish)
# PAST         the slot is over
# OUT_OF_SERVICE  the charger is broken or switched off
BlockState = Literal["FREE", "BOOKED", "HELD", "PAST", "OUT_OF_SERVICE"]


class AvailabilityBlock(BaseModel):
    start: dt.datetime  # UTC; the slot is [start, end)
    end: dt.datetime
    state: BlockState


class ChargerAvailability(BaseModel):
    charger_id: UUID
    label: str
    connector_type: str
    power_kw: float | None = None
    price_per_kwh: float | None = None
    status: str
    is_estimated: bool
    blocks: list[AvailabilityBlock]


class StationAvailability(BaseModel):
    station_id: UUID
    date: dt.date  # the India-time (IST) day shown
    timezone: str
    slot_minutes: int
    now: dt.datetime  # the server's clock, so the page can draw a "now" line without trusting the browser
    chargers: list[ChargerAvailability]
