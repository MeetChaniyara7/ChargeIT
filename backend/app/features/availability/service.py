"""The 30-minute availability grid for one station on one day (IST).

All the "is it free?" decisions happen here, on the server. The web app only draws them.
"""

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BOOKING_RULES
from app.core.errors import AppError
from app.core.slots import day_blocks, ist_date
from app.features.availability.occupancy import UNUSABLE_STATUSES, bookings_overlapping
from app.features.availability.schemas import (
    AvailabilityBlock, BlockState, ChargerAvailability, StationAvailability,
)
from app.features.charging.models import ChargingSession
from app.features.jobs.lazy import run_due_jobs
from app.features.stations import repository

# One day back is allowed (to show what just happened), nothing older.
DAYS_BACK = 1


def check_date_in_range(day: date, now: datetime) -> None:
    today = ist_date(now)
    if not (today - timedelta(days=DAYS_BACK) <= day <= today + timedelta(days=BOOKING_RULES.max_days_ahead)):
        raise AppError(
            422,
            "DATE_OUT_OF_RANGE",
            f"Availability is shown from yesterday to {BOOKING_RULES.max_days_ahead} days ahead.",
        )


def _state(
    block_start: datetime, block_end: datetime, usable: bool, now: datetime, bookings: list[tuple[str, datetime, datetime]],
    busy_outside: bool = False,
) -> BlockState:
    if block_end <= now:
        return "PAST"
    if not usable:
        return "OUT_OF_SERVICE"
    if busy_outside and block_start <= now < block_end:
        return "BUSY_EXTERNAL"  # someone is charging with the operator's own app or card right now
    overlapping = [status for status, b_start, b_end in bookings if b_start < block_end and b_end > block_start]
    if not overlapping:
        return "FREE"
    # A confirmed/active booking wins over someone else's unpaid hold.
    return "HELD" if all(status == "HELD" for status in overlapping) else "BOOKED"


def station_availability(db: Session, station_id: UUID, day: date, now: datetime) -> StationAvailability:
    check_date_in_range(day, now)
    station = repository.get_station(db, station_id)
    if not station or not station.is_active:
        raise AppError(404, "STATION_NOT_FOUND", "Station not found.")

    # Lazy checks: holds that ran out, missed codes, sessions past their end, occupied chargers are dealt
    # with now, so the grid is right even if the minute-by-minute job has not run yet.
    run_due_jobs(db, now, station_id)
    station = repository.get_station(db, station_id)

    blocks = day_blocks(day)
    day_start, day_end = blocks[0][0], blocks[-1][1]

    # ONE query for every booking that touches this station's chargers today.
    by_charger: dict[UUID, list[tuple[str, datetime, datetime]]] = {}
    for charger_id, status, start, end in bookings_overlapping(db, [c.charger_id for c in station.chargers], day_start, day_end, now):
        by_charger.setdefault(charger_id, []).append((status, start, end))

    # Chargers an outside session is using right now (ONE query): their current block is BUSY_EXTERNAL.
    busy_outside = set(db.scalars(
        select(ChargingSession.charger_id).where(
            ChargingSession.charger_id.in_([c.charger_id for c in station.chargers]),
            ChargingSession.ended_at.is_(None), ChargingSession.source == "EXTERNAL",
        )
    ))

    chargers = [
        ChargerAvailability(
            charger_id=c.charger_id,
            label=c.label,
            connector_type=c.connector_type,
            power_kw=float(c.power_kw) if c.power_kw is not None else None,
            price_per_kwh=float(c.price_per_kwh) if c.price_per_kwh is not None else None,
            status=c.status,
            is_estimated=c.is_estimated,
            blocks=[
                AvailabilityBlock(
                    start=start, end=end,
                    state=_state(start, end, c.status not in UNUSABLE_STATUSES, now, by_charger.get(c.charger_id, []), c.charger_id in busy_outside),
                )
                for start, end in blocks
            ],
        )
        for c in station.chargers
    ]
    return StationAvailability(
        station_id=station.station_id, date=day, timezone="Asia/Kolkata",
        slot_minutes=BOOKING_RULES.slot_minutes, now=now, chargers=chargers,
    )

