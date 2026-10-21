"""Charging sessions: starting one, the live numbers, and stopping.

Live numbers are computed here, on the server, with the same formula the background jobs use
(energy.py mirrors the SQL function `session_energy_kwh`). The web page only draws them.
Starting a session is what the kiosk does after a correct code (Phase 6); until then the admin
"simulate" button calls the same function.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import CHARGING_RULES
from app.core.errors import AppError
from app.features.bookings import state_machine
from app.features.bookings.models import Booking
from app.features.bookings.schemas import BookingCharger, BookingStation
from app.features.charging import energy
from app.features.charging.models import ChargingSession
from app.features.charging.schemas import LiveSession
from app.features.jobs.lazy import run_due_jobs
from app.features.stations.models import Charger, Station
from app.features.vehicles.models import Vehicle

Row = tuple[ChargingSession, Booking, Charger, Station, "Decimal | None"]


def _load(db: Session, user_id: UUID, session_id: UUID) -> Row:
    row = db.execute(
        select(ChargingSession, Booking, Charger, Station, Vehicle.battery_kwh)
        .join(Booking, Booking.booking_id == ChargingSession.booking_id)
        .join(Charger, Charger.charger_id == ChargingSession.charger_id)
        .join(Station, Station.station_id == Charger.station_id)
        .outerjoin(Vehicle, Vehicle.vehicle_id == Booking.vehicle_id)
        .where(ChargingSession.session_id == session_id, Booking.user_id == user_id)
    ).first()
    if row is None:
        raise AppError(404, "SESSION_NOT_FOUND", "Charging session not found.")
    return tuple(row)  # type: ignore[return-value]


def _load_fresh(db: Session, user_id: UUID, session_id: UUID, now: datetime) -> Row:
    """The session after the lazy job check for its station, so a stop that is due has already happened."""
    _, _, _, station, _ = _load(db, user_id, session_id)
    run_due_jobs(db, now, station.station_id)
    return _load(db, user_id, session_id)


def to_live(db: Session, row: Row, now: datetime) -> LiveSession:
    session, booking, charger, station, battery = row
    running = session.ended_at is None
    until = now if running else session.ended_at
    kwh = (
        energy.energy_kwh(charger.power_kw, session.started_at, until, battery, session.start_soc_percent)
        if running
        else Decimal(session.energy_kwh)
    )
    planned = booking.end if booking is not None else None
    seconds_left = max(0, int((planned - now).total_seconds())) if running and planned is not None else None
    cost = energy.bill_amount(kwh, charger.price_per_kwh) if running or session.bill_amount is None else Decimal(session.bill_amount)

    waiting = False
    if running and planned is not None:
        next_start = db.scalar(
            select(func.min(func.lower(Booking.time_range))).where(
                Booking.charger_id == charger.charger_id, Booking.status == "CONFIRMED", func.lower(Booking.time_range) >= planned
            )
        )
        waiting = next_start is not None and next_start <= planned + timedelta(minutes=CHARGING_RULES.next_booking_waiting_minutes)

    return LiveSession(
        session_id=session.session_id,
        booking_id=session.booking_id,
        status="RUNNING" if running else "ENDED",
        source=session.source,
        station=BookingStation(
            station_id=station.station_id, name=station.name, address=station.address, city=station.city,
            latitude=station.latitude, longitude=station.longitude,
        ),
        charger=BookingCharger(
            charger_id=charger.charger_id, label=charger.label, connector_type=charger.connector_type,
            power_kw=float(charger.power_kw) if charger.power_kw is not None else None,
            price_per_kwh=float(charger.price_per_kwh) if charger.price_per_kwh is not None else None,
        ),
        started_at=session.started_at,
        planned_stop_at=planned,
        server_time=now,
        seconds_left=seconds_left,
        energy_kwh=float(kwh),
        battery_percent=energy.battery_percent(kwh, battery, session.start_soc_percent),
        cost_so_far=float(cost),
        ended_at=session.ended_at,
        end_reason=session.end_reason,
        duration_minutes=round(max((until - session.started_at).total_seconds(), 0) / 60, 1),
        bill_amount=float(session.bill_amount) if session.bill_amount is not None else None,
        bill_status=session.bill_status,
        stop_warning=running and seconds_left is not None and seconds_left <= CHARGING_RULES.stop_warning_minutes * 60,
        next_booking_waiting=waiting,
        can_stop=running and session.source != "EXTERNAL",
    )


def get_session(db: Session, user_id: UUID, session_id: UUID, now: datetime) -> LiveSession:
    return to_live(db, _load_fresh(db, user_id, session_id, now), now)


def active_session(db: Session, user_id: UUID, now: datetime) -> LiveSession | None:
    """The driver's running session, if any (for the Charging tab and the pill in the app bar)."""
    found = db.scalar(
        select(ChargingSession.session_id)
        .join(Booking, Booking.booking_id == ChargingSession.booking_id)
        .where(Booking.user_id == user_id, ChargingSession.ended_at.is_(None))
        .order_by(ChargingSession.started_at.desc())
        .limit(1)
    )
    return get_session(db, user_id, found, now) if found else None


def stop_session(db: Session, user_id: UUID, session_id: UUID, now: datetime) -> LiveSession:
    """The driver stops charging. The bill is worked out up to now. Stopping twice is harmless."""
    row = _load_fresh(db, user_id, session_id, now)
    if row[0].ended_at is None:
        db.execute(
            text("SELECT finish_session(CAST(:s AS uuid), CAST(:at AS timestamptz), 'USER_STOP', 'USER', CAST(:now AS timestamptz))"),
            {"s": session_id, "at": now, "now": now},
        )
        db.commit()
        row = _load(db, user_id, session_id)
    return to_live(db, row, now)


def start_session(db: Session, booking_id: UUID, now: datetime, actor: str = "DEVICE", device_id: UUID | None = None) -> ChargingSession:
    """Start charging for a confirmed booking (what the kiosk does after a correct code).

    The booking goes CONFIRMED -> ACTIVE, the code is marked used, the charger goes to CHARGING and a
    session begins. Refuses a booking that is not confirmed or a charger that cannot charge.
    """
    booking = db.scalars(select(Booking).where(Booking.booking_id == booking_id).with_for_update()).first()
    if booking is None:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found.")
    if booking.status != "CONFIRMED":
        raise AppError(409, "BOOKING_NOT_STARTABLE", f"A {booking.status.lower().replace('_', ' ')} booking cannot start charging.")
    charger = db.scalars(select(Charger).where(Charger.charger_id == booking.charger_id).with_for_update()).one()
    if charger.status not in ("AVAILABLE", "RESERVED"):
        raise AppError(409, "CHARGER_UNAVAILABLE", f"The charger cannot start charging right now ({charger.status.lower().replace('_', ' ')}).")

    state_machine.transition(db, booking, "ACTIVE", actor, "Charging started")
    booking.otp_used_at = now
    session = ChargingSession(
        booking_id=booking.booking_id, charger_id=charger.charger_id, device_id=device_id, source="BOOKING", started_at=now,
        start_soc_percent=CHARGING_RULES.default_start_soc_percent,
    )
    db.add(session)
    db.execute(
        text("SELECT apply_charger_event(CAST(:c AS uuid), 'SESSION_START', CAST('{}' AS jsonb), 'SYSTEM', CAST(:now AS timestamptz))"),
        {"c": charger.charger_id, "now": now},
    )
    db.flush()
    db.commit()
    return session
