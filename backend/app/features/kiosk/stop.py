"""Stopping a walk-in early at the kiosk, and getting the unused money back.

A walk-in has no account, so nothing ties the session to a person except the stop code they were given when they
started (shown once, stored only as an HMAC like a booking code). Typing it stops that session: the energy used is
billed (never more than they prepaid) and the rest is recorded as a refund, exactly as when the money runs out.
Wrong codes count towards the same cooldown and alert as wrong booking codes, so nobody can guess their way into
stopping a stranger session.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.features.bookings import otp
from app.features.bookings.models import Booking
from app.features.charging.models import ChargingSession
from app.features.jobs.lazy import run_due_jobs
from app.features.kiosk import service
from app.features.kiosk.models import StationDevice
from app.features.kiosk.schemas import WalkInStopOut
from app.features.payments.models import Payment
from app.features.stations.models import Charger


def stop_walk_in(db: Session, device: StationDevice, code: str, now: datetime) -> WalkInStopOut:
    wait = service.cooldown_left(db, device, now)
    if wait:
        raise AppError(429, "OTP_COOLDOWN", "Too many wrong codes. Please wait a moment.", {"retry_after_seconds": wait})

    run_due_jobs(db, now, device.station_id)  # a walk-in that already ended by itself is not stoppable (and not found below)
    code = code.strip()
    running = db.execute(
        select(Booking, ChargingSession, Charger)
        .join(ChargingSession, ChargingSession.booking_id == Booking.booking_id)
        .join(Charger, Charger.charger_id == Booking.charger_id)
        .where(
            Charger.station_id == device.station_id, Booking.source == "WALK_IN", Booking.status == "ACTIVE",
            ChargingSession.ended_at.is_(None), Booking.otp_hash.is_not(None),
        )
    ).all()  # this station only: a code from another station can never match here
    found = next(((b, s, c) for b, s, c in running if otp.matches(code, b.otp_hash)), None)
    if found is None:
        raise service.wrong_try(db, device, now)

    booking, session, charger = found
    db.execute(
        text("SELECT finish_session(CAST(:s AS uuid), CAST(:at AS timestamptz), 'USER_STOP', 'DEVICE', CAST(:at AS timestamptz))"),
        {"s": session.session_id, "at": now},
    )
    service._record(db, device, True, now)  # a right code: the guessing streak starts again
    db.commit()
    db.refresh(session)
    payment = db.scalar(select(Payment).where(Payment.booking_id == booking.booking_id, Payment.purpose == "WALKIN_PREPAID"))
    return WalkInStopOut(
        charger_label=charger.label,
        prepaid=float(session.prepaid_amount or 0),
        used=float(session.bill_amount or 0),
        refunded=float(Decimal(payment.refunded_amount)) if payment else 0,
    )
