"""The kiosk's status board and "start with a code".

The board is shared by everyone standing at the station, so it shows chargers and money for walk-ins
only: never a name, a phone number, or an app user's bill.

Wrong codes: after 5 wrong tries in a row the kiosk waits 2 minutes (so one person cannot lock
everybody out for good). 20 or more wrong tries in 10 minutes also raises an alert for the admin.
"""

from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BOOKING_RULES
from app.core.errors import AppError
from app.features.availability.occupancy import occupies_charger
from app.features.bookings import otp
from app.features.bookings.instant import instant_window
from app.features.bookings.models import Booking
from app.features.charging import energy, service as charging
from app.features.charging.models import ChargingSession
from app.features.jobs.lazy import run_due_jobs
from app.features.kiosk.models import AdminAlert, OtpAttempt, StationDevice
from app.features.kiosk.schemas import (
    ChargerTile, KioskStatus, OtpStartOut, WalkInDone, WalkInOption, WalkInProgress,
)
from app.features.payments.models import Payment
from app.features.stations.models import Charger, Station
from app.features.vehicles.models import Vehicle


# ---------------------------------------------------------------- walk-in price options

def until_next_amount(charger: Charger, start: datetime, end: datetime) -> int:
    """What it costs to charge for the whole window: the energy the window allows x the price, rounded up to a whole rupee."""
    kwh = energy.energy_kwh(charger.power_kw, start, end)
    return max(1, int(energy.bill_amount(kwh, charger.price_per_kwh).to_integral_value(rounding=ROUND_CEILING)))


def kwh_for_amount(charger: Charger, amount: int, start: datetime, end: datetime) -> float:
    """About how much energy an amount buys, never more than the window allows."""
    by_money = Decimal(amount) / Decimal(str(charger.price_per_kwh))
    by_window = energy.energy_kwh(charger.power_kw, start, end)
    return float(min(by_money, by_window).quantize(Decimal("0.1")))


def build_options(charger: Charger, window: tuple[datetime, datetime]) -> list[WalkInOption]:
    start, end = window
    options = [
        WalkInOption(kind="AMOUNT", amount=a, kwh=kwh_for_amount(charger, a, start, end)) for a in BOOKING_RULES.walkin_amounts_inr
    ]
    full = until_next_amount(charger, start, end)
    options.append(WalkInOption(kind="UNTIL_NEXT", amount=full, kwh=kwh_for_amount(charger, full, start, end), until=end))
    return options


def walk_in_blocker(charger: Charger, booked_now: bool, window) -> str | None:
    """Why a charger cannot take a walk-in right now (None = it can)."""
    if charger.price_per_kwh is None or Decimal(str(charger.price_per_kwh)) <= 0:
        return "PRICE_UNKNOWN"
    if not charger.power_kw:
        return "POWER_UNKNOWN"
    if booked_now:
        return "BOOKED_NOW"
    if window is None:
        return "BOOKING_SOON"
    return None


# ---------------------------------------------------------------- the status board

def status(db: Session, device: StationDevice, now: datetime) -> KioskStatus:
    run_due_jobs(db, now, device.station_id)  # holds that ran out, sessions that must stop, chargers to reserve
    station = db.get(Station, device.station_id)
    chargers = db.scalars(select(Charger).where(Charger.station_id == device.station_id).order_by(Charger.label)).all()
    ids = [c.charger_id for c in chargers]
    if not ids:
        return KioskStatus(station_name=station.name, server_time=now, idle_reset_seconds=BOOKING_RULES.kiosk_idle_reset_seconds, chargers=[])

    live = db.execute(
        select(Booking.charger_id, Booking.status, Booking.source, Booking.time_range)
        .where(Booking.charger_id.in_(ids), occupies_charger(now), func.upper(Booking.time_range) > now)
    ).all()
    running = {
        s.charger_id: (s, battery, booking_range)
        for s, battery, booking_range in db.execute(
            select(ChargingSession, Vehicle.battery_kwh, Booking.time_range)
            .outerjoin(Booking, Booking.booking_id == ChargingSession.booking_id)
            .outerjoin(Vehicle, Vehicle.vehicle_id == Booking.vehicle_id)
            .where(ChargingSession.charger_id.in_(ids), ChargingSession.ended_at.is_(None))
        ).all()
    }
    done_since = now - timedelta(seconds=BOOKING_RULES.kiosk_done_tile_seconds)
    finished = {
        s.charger_id: s
        for s in db.scalars(
            select(ChargingSession)
            .where(ChargingSession.charger_id.in_(ids), ChargingSession.source == "WALK_IN", ChargingSession.ended_at >= done_since)
            .order_by(ChargingSession.ended_at)
        ).all()
    }
    refunds: dict = {}
    if finished:
        rows = db.execute(
            select(Payment.booking_id, Payment.refunded_amount).where(
                Payment.booking_id.in_([s.booking_id for s in finished.values()]), Payment.purpose == "WALKIN_PREPAID"
            )
        ).all()
        refunds = {b: Decimal(r) for b, r in rows}

    tiles = [
        _tile(c, [x for x in live if x.charger_id == c.charger_id], running.get(c.charger_id), finished.get(c.charger_id), refunds, now)
        for c in chargers
    ]
    return KioskStatus(
        station_name=station.name, server_time=now, idle_reset_seconds=BOOKING_RULES.kiosk_idle_reset_seconds, chargers=tiles
    )


def _tile(charger: Charger, live: list, running, finished, refunds: dict, now: datetime) -> ChargerTile:
    base = dict(
        charger_id=charger.charger_id, label=charger.label, connector_type=charger.connector_type,
        power_kw=float(charger.power_kw) if charger.power_kw is not None else None,
        price_per_kwh=float(charger.price_per_kwh) if charger.price_per_kwh is not None else None,
    )
    done = None
    if finished is not None:
        done = WalkInDone(
            used=float(Decimal(finished.bill_amount or 0)), refunded=float(refunds.get(finished.booking_id, Decimal(0))),
            ended_at=finished.ended_at,
        )

    if charger.status in ("FAULTED", "OUT_OF_SERVICE"):
        return ChargerTile(**base, state="OUT_OF_SERVICE", last_walk_in=done)

    if running is not None:
        session, battery, booking_range = running
        kwh = energy.energy_kwh(charger.power_kw, session.started_at, now, battery, session.start_soc_percent)
        progress = None if session.source == "EXTERNAL" else energy.battery_percent(kwh, battery, session.start_soc_percent)
        walk_in = None
        if session.source == "WALK_IN" and session.prepaid_amount is not None:
            spent = min(energy.bill_amount(kwh, charger.price_per_kwh), Decimal(session.prepaid_amount))
            walk_in = WalkInProgress(prepaid=float(session.prepaid_amount), used=float(spent))
        return ChargerTile(
            **base, state="CHARGING", progress_percent=progress, walk_in=walk_in,
            ends_at=booking_range.upper if booking_range is not None else None,
        )

    covering = [x for x in live if x.time_range.lower <= now < x.time_range.upper]
    upcoming = sorted((x for x in live if x.time_range.lower > now), key=lambda x: x.time_range.lower)
    next_start = upcoming[0].time_range.lower if upcoming else None

    if any(x.source == "WALK_IN" and x.status == "HELD" for x in covering):
        return ChargerTile(**base, state="PAYING", last_walk_in=done)

    window = instant_window(now, next_start)
    reason = walk_in_blocker(charger, bool(covering), window)
    options = build_options(charger, window) if reason is None else []
    free_until = next_start - timedelta(minutes=BOOKING_RULES.buffer_before_next_booking) if next_start and not covering else None

    if charger.status == "RESERVED" or covering:
        keeper = covering[0] if covering else (upcoming[0] if upcoming else None)
        return ChargerTile(
            **base, state="RESERVED", reserved_for=keeper.time_range.lower if keeper else None, free_until=free_until,
            last_walk_in=done, can_walk_in=reason is None, walk_in_blocked_reason=reason, options=options,
        )
    return ChargerTile(
        **base, state="FREE", free_until=free_until, last_walk_in=done,
        can_walk_in=reason is None, walk_in_blocked_reason=reason, options=options,
    )


# ---------------------------------------------------------------- start with a code

def _record(db: Session, device: StationDevice, success: bool, now: datetime) -> None:
    db.add(OtpAttempt(device_id=device.device_id, success=success, created_at=now))
    db.flush()


def _wrong_streak(db: Session, device: StationDevice) -> tuple[int, datetime | None]:
    """How many wrong tries in a row since the last right one, and when the latest was."""
    last_ok = db.scalar(select(func.max(OtpAttempt.created_at)).where(OtpAttempt.device_id == device.device_id, OtpAttempt.success.is_(True)))
    query = select(func.count(), func.max(OtpAttempt.created_at)).where(OtpAttempt.device_id == device.device_id, OtpAttempt.success.is_(False))
    if last_ok is not None:
        query = query.where(OtpAttempt.created_at > last_ok)
    count, latest = db.execute(query).one()
    return count, latest


def cooldown_left(db: Session, device: StationDevice, now: datetime) -> int:
    """Seconds the kiosk must wait before it takes another code (0 = free to try)."""
    count, latest = _wrong_streak(db, device)
    if count == 0 or count % BOOKING_RULES.kiosk_wrong_otp_limit != 0 or latest is None:
        return 0
    until = latest + timedelta(minutes=BOOKING_RULES.kiosk_cooldown_minutes)
    return int((until - now).total_seconds() + 0.999) if until > now else 0


def _raise_alert_if_needed(db: Session, device: StationDevice, now: datetime) -> None:
    window = timedelta(minutes=BOOKING_RULES.kiosk_alert_window_minutes)
    wrong = db.scalar(
        select(func.count()).where(OtpAttempt.device_id == device.device_id, OtpAttempt.success.is_(False), OtpAttempt.created_at > now - window)
    )
    if wrong < BOOKING_RULES.kiosk_alert_threshold:
        return
    already = db.scalar(
        select(func.count()).where(
            AdminAlert.device_id == device.device_id, AdminAlert.kind == "KIOSK_OTP_GUESSING", AdminAlert.created_at > now - window
        )
    )
    if not already:
        db.add(AdminAlert(
            kind="KIOSK_OTP_GUESSING", station_id=device.station_id, device_id=device.device_id, created_at=now,
            message=f"{wrong} wrong codes in {BOOKING_RULES.kiosk_alert_window_minutes} minutes at kiosk '{device.name}'. Someone may be guessing codes.",
            details={"wrong_tries": wrong, "window_minutes": BOOKING_RULES.kiosk_alert_window_minutes},
        ))


def wrong_try(db: Session, device: StationDevice, now: datetime, *, right_code_wrong_time: bool = False) -> AppError:
    """Counts a wrong code (for the cooldown and the alert) and returns the error to raise. Used by every code pad on the kiosk."""
    _record(db, device, False, now)
    _raise_alert_if_needed(db, device, now)
    streak, _ = _wrong_streak(db, device)
    left = BOOKING_RULES.kiosk_wrong_otp_limit - (streak % BOOKING_RULES.kiosk_wrong_otp_limit)
    db.commit()
    if left == BOOKING_RULES.kiosk_wrong_otp_limit:  # that was the last try of the block
        return AppError(
            429, "OTP_COOLDOWN", "Too many wrong codes. Please wait a moment.",
            {"retry_after_seconds": BOOKING_RULES.kiosk_cooldown_minutes * 60},
        )
    if right_code_wrong_time:  # the right code, but outside its time window
        return AppError(
            409, "OTP_NOT_VALID_NOW", "This code works from 15 minutes before your slot until 10 minutes after it starts.",
            {"tries_left": left},
        )
    return AppError(400, "WRONG_OTP", "That code is not right.", {"tries_left": left})


def otp_start(db: Session, device: StationDevice, code: str, now: datetime) -> OtpStartOut:
    """A driver types the code from their booking: start that booking's charger."""
    wait = cooldown_left(db, device, now)
    if wait:
        raise AppError(429, "OTP_COOLDOWN", "Too many wrong codes. Please wait a moment.", {"retry_after_seconds": wait})

    run_due_jobs(db, now, device.station_id)
    code = code.strip()
    candidates = db.execute(
        select(Booking, Charger)
        .join(Charger, Charger.charger_id == Booking.charger_id)
        .where(Charger.station_id == device.station_id, Booking.status == "CONFIRMED", Booking.otp_hash.is_not(None), Booking.otp_used_at.is_(None))
    ).all()  # only this station's bookings: a code from another station can never match here
    found = next(((b, c) for b, c in candidates if otp.matches(code, b.otp_hash)), None)

    if found is None or not otp.is_valid_now(found[0].start, now, found[0].otp_used_at):
        raise wrong_try(db, device, now, right_code_wrong_time=found is not None)

    booking, charger = found
    try:
        session = charging.start_session(db, booking.booking_id, now, actor="DEVICE", device_id=device.device_id)
    except AppError:
        db.rollback()
        _record(db, device, True, now)  # the code was right: a charger problem is not a guess
        db.commit()
        raise
    _record(db, device, True, now)
    db.commit()
    return OtpStartOut(
        charger_id=charger.charger_id, charger_label=charger.label, connector_type=charger.connector_type, session_id=session.session_id
    )
