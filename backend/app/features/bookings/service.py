"""Booking rules: holding a slot, "Charge now", cancelling, new codes.

Every status change goes through state_machine.transition(). Overlaps are decided by the
database's exclusion constraint: we just try the insert and turn its refusal (23P01) into
"slot just taken" with alternatives. A deadlock (40P01) between two simultaneous bookings is
retried once; the retry then gets a clean 23P01.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, joinedload

from app.config import BOOKING_RULES
from app.core.errors import AppError
from app.core.slots import SLOT, as_utc, is_slot_aligned
from app.features.availability.occupancy import UNUSABLE_STATUSES, occupies_charger
from app.features.bookings import alternatives, otp, refunds, state_machine
from app.features.bookings.instant import instant_window
from app.features.bookings.models import Booking
from app.features.bookings.schemas import (
    BookingCharger, BookingOut, BookingStation, DueItem, DuesOut, InstantBookingOut, OtpOut, RefundPreview,
)
from app.features.charging.models import ChargingSession
from app.features.jobs.lazy import run_due_jobs, run_for_stations
from app.features.payments.models import Payment
from app.features.stations.models import Charger, Station
from app.features.vehicles import service as vehicles

EXCLUSION_VIOLATION = "23P01"  # two live bookings would overlap on one charger
UNIQUE_VIOLATION = "23505"
DEADLOCK = "40P01"
HOLD_INDEX = "bookings_one_hold_per_user"
LIVE = ("HELD", "CONFIRMED", "ACTIVE")


def sqlstate(exc: BaseException) -> str | None:
    return getattr(getattr(exc, "orig", None), "sqlstate", None)


def blocks_in(start: datetime, end: datetime) -> int:
    return max(1, -(-int((end - start).total_seconds()) // int(SLOT.total_seconds())))


# ---------------------------------------------------------------- reading

def _loaders():
    return joinedload(Booking.charger).joinedload(Charger.station)


def effective_status(booking: Booking, now: datetime) -> str:
    """A hold whose time ran out is EXPIRED the moment anyone looks, before the job marks it."""
    if booking.status == "HELD" and booking.hold_expires_at is not None and booking.hold_expires_at <= now:
        return "EXPIRED"
    return booking.status


def fee_paid_amount(payment: Payment | None) -> Decimal:
    """What the driver actually paid for this booking (nothing until the payment is captured)."""
    if payment is not None and payment.status in ("CAPTURED", "PARTIALLY_REFUNDED", "REFUNDED"):
        return Decimal(payment.amount)
    return Decimal(0)


def booking_payment(db: Session, booking_id: UUID) -> Payment | None:
    return db.scalar(
        select(Payment)
        .where(Payment.booking_id == booking_id, Payment.purpose == "BOOKING_FEE")
        .order_by(Payment.created_at.desc())
        .limit(1)
    )


def to_out(booking: Booking, payment: Payment | None, now: datetime, session_id: UUID | None = None) -> BookingOut:
    charger = booking.charger
    station = charger.station
    status = effective_status(booking, now)
    opens, closes = otp.window(booking.start)
    return BookingOut(
        booking_id=booking.booking_id, status=status, source=booking.source, start=booking.start, end=booking.end,
        blocks=blocks_in(booking.start, booking.end),
        hold_expires_at=booking.hold_expires_at if status == "HELD" else None, server_time=now,
        booking_fee=float(booking.booking_fee), fee_paid=fee_paid_amount(payment) > 0,
        refund_amount=float(booking.refund_amount), cancelled_at=booking.cancelled_at, cancel_reason=booking.cancel_reason,
        created_at=booking.created_at,
        station=BookingStation(
            station_id=station.station_id, name=station.name, address=station.address, city=station.city,
            latitude=station.latitude, longitude=station.longitude,
        ),
        charger=BookingCharger(
            charger_id=charger.charger_id, label=charger.label, connector_type=charger.connector_type,
            power_kw=float(charger.power_kw) if charger.power_kw is not None else None,
            price_per_kwh=float(charger.price_per_kwh) if charger.price_per_kwh is not None else None,
        ),
        code_valid_from=opens, code_valid_until=closes, has_code=booking.otp_hash is not None,
        code_used=booking.otp_used_at is not None,
        can_cancel=status in ("HELD", "CONFIRMED"),
        can_show_new_code=status == "CONFIRMED" and booking.otp_used_at is None and as_utc(now) <= closes,
        notice_kind=booking.notice_kind, notice_text=booking.notice_text, session_id=session_id,
    )


def sessions_by_booking(db: Session, booking_ids: list[UUID]) -> dict[UUID, UUID]:
    """booking id -> its charging session id, for the bookings that have started charging (one query)."""
    if not booking_ids:
        return {}
    return dict(db.execute(select(ChargingSession.booking_id, ChargingSession.session_id).where(ChargingSession.booking_id.in_(booking_ids))).all())


def get_owned(db: Session, user_id: UUID, booking_id: UUID, *, lock: bool = False) -> Booking:
    stmt = select(Booking).options(_loaders()).where(Booking.booking_id == booking_id, Booking.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update(of=Booking)
    booking = db.scalars(stmt).unique().first()
    if not booking:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found.")
    return booking


def get_booking(db: Session, user_id: UUID, booking_id: UUID, now: datetime) -> BookingOut:
    run_due_jobs(db, now, get_owned(db, user_id, booking_id).charger.station_id)  # lazy checks: moves, no-shows, auto-stops
    booking = get_owned(db, user_id, booking_id, lock=True)
    expire_if_stale(db, booking, now)
    session = sessions_by_booking(db, [booking.booking_id]).get(booking.booking_id)
    return to_out(booking, booking_payment(db, booking.booking_id), now, session)


def my_bookings(db: Session, user_id: UUID, scope: str, now: datetime, limit: int = 100) -> list[BookingOut]:
    """Upcoming: still holding a charger and not over. Past: everything else."""
    # Lazy checks first, for the stations this driver has live bookings at, so what they see is right.
    run_for_stations(db, now, db.scalars(
        select(Charger.station_id).join(Booking, Booking.charger_id == Charger.charger_id)
        .where(Booking.user_id == user_id, Booking.status.in_(LIVE)).distinct()
    ))
    still_live = and_(
        Booking.status.in_(LIVE),
        func.upper(Booking.time_range) > now,
        or_(Booking.status != "HELD", Booking.hold_expires_at > now),
    )
    stmt = select(Booking).options(_loaders()).where(Booking.user_id == user_id)
    if scope == "upcoming":
        stmt = stmt.where(still_live).order_by(func.lower(Booking.time_range))
    else:
        stmt = stmt.where(not_(still_live)).order_by(func.lower(Booking.time_range).desc())
    bookings = list(db.scalars(stmt.limit(limit)).unique())

    payments: dict[UUID, Payment] = {}
    if bookings:
        for p in db.scalars(
            select(Payment).where(Payment.booking_id.in_([b.booking_id for b in bookings]), Payment.purpose == "BOOKING_FEE")
            .order_by(Payment.created_at)
        ):
            payments[p.booking_id] = p  # the newest wins
    sessions = sessions_by_booking(db, [b.booking_id for b in bookings])
    return [to_out(b, payments.get(b.booking_id), now, sessions.get(b.booking_id)) for b in bookings]


def unpaid_bills(db: Session, user_id: UUID) -> DuesOut:
    """Energy bills the user has not paid yet. While any exist, new bookings are blocked."""
    rows = db.execute(
        select(ChargingSession, Station.name)
        .join(Booking, Booking.booking_id == ChargingSession.booking_id)
        .join(Charger, Charger.charger_id == ChargingSession.charger_id)
        .join(Station, Station.station_id == Charger.station_id)
        .where(Booking.user_id == user_id, ChargingSession.bill_status == "DUE")
        .order_by(ChargingSession.ended_at.desc())
    ).all()
    items = [
        DueItem(
            session_id=s.session_id, booking_id=s.booking_id, station_name=name,
            amount=float(s.bill_amount or 0), ended_at=s.ended_at,
        )
        for s, name in rows
    ]
    return DuesOut(count=len(items), total=round(sum(i.amount for i in items), 2), items=items)


# ---------------------------------------------------------------- lazy expiry

def expire_if_stale(db: Session, booking: Booking, now: datetime) -> None:
    if booking.status == "HELD" and effective_status(booking, now) == "EXPIRED":
        state_machine.transition(db, booking, "EXPIRED", "SYSTEM", "Hold ran out")
        db.commit()


def expire_stale_holds(db: Session, now: datetime, *, charger_id: UUID | None = None, user_id: UUID | None = None) -> int:
    """Mark old unpaid holds EXPIRED so they stop blocking the charger / the user's one-hold limit.

    Done inside the booking transaction, so correctness never depends on when the background job last ran.
    """
    scope = []
    if charger_id is not None:
        scope.append(Booking.charger_id == charger_id)
    if user_id is not None:
        scope.append(Booking.user_id == user_id)
    conditions = [Booking.status == "HELD", Booking.hold_expires_at <= now]
    if scope:
        conditions.append(or_(*scope))
    stale = list(db.scalars(select(Booking).where(*conditions).order_by(Booking.booking_id).with_for_update()))
    for booking in stale:
        state_machine.transition(db, booking, "EXPIRED", "SYSTEM", "Hold ran out")
    return len(stale)


# ---------------------------------------------------------------- shared checks

def _charger_for_booking(db: Session, charger_id: UUID) -> Charger:
    charger = db.scalars(
        select(Charger).options(joinedload(Charger.station)).where(Charger.charger_id == charger_id)
    ).unique().first()
    if not charger or not charger.station.is_active or charger.station.vehicle_category != "FOUR_WHEELER":
        raise AppError(404, "CHARGER_NOT_FOUND", "Charger not found.")
    if charger.status in UNUSABLE_STATUSES:
        raise AppError(409, "CHARGER_OUT_OF_SERVICE", "This charger is out of service right now.")
    return charger


def _check_vehicle(db: Session, user_id: UUID, vehicle_id: UUID | None, charger: Charger) -> None:
    if vehicle_id is None:
        return
    vehicle = vehicles.get_owned(db, user_id, vehicle_id)
    if vehicle.connector_type != charger.connector_type:
        raise AppError(
            422, "INCOMPATIBLE_VEHICLE",
            f"{vehicle.nickname} uses {vehicle.connector_type}, but this charger is {charger.connector_type}.",
        )


def _check_no_dues(db: Session, user_id: UUID) -> None:
    dues = unpaid_bills(db, user_id)
    if dues.count:
        raise AppError(
            409, "UNPAID_BILL", f"Pay your pending bill of ₹{dues.total:.2f} before booking again.",
            {"count": dues.count, "total": dues.total},
        )


def _active_hold(db: Session, user_id: UUID, now: datetime) -> Booking | None:
    return db.scalars(
        select(Booking).options(_loaders()).where(Booking.user_id == user_id, Booking.status == "HELD", Booking.hold_expires_at > now)
    ).unique().first()


def _active_hold_error(db: Session, user_id: UUID, now: datetime) -> AppError:
    hold = _active_hold(db, user_id, now)
    return AppError(
        409, "ACTIVE_HOLD_EXISTS", "You already have a slot waiting for payment. Finish or cancel it first.",
        {"booking_id": str(hold.booking_id)} if hold else None,
    )


def taken_code_hashes(db: Session, station_id: UUID, start: datetime) -> list[str]:
    """Stored code hashes of other bookings at this station whose code windows overlap one starting at `start`."""
    rows = db.execute(
        select(Booking.otp_hash, func.lower(Booking.time_range))
        .join(Charger, Charger.charger_id == Booking.charger_id)
        .where(
            Charger.station_id == station_id, Booking.status == "CONFIRMED",
            Booking.otp_hash.is_not(None), Booking.otp_used_at.is_(None),
        )
    ).all()
    return [h for h, other_start in rows if otp.windows_overlap(start, other_start)]


def issue_code(db: Session, booking: Booking) -> str:
    """A new code for a booking (replacing any old one). Returns the plain code: the only time it exists."""
    code, digest = otp.generate(taken_code_hashes(db, booking.charger.station_id, booking.start))
    booking.otp_hash = digest
    booking.otp_used_at = None
    db.flush()
    return code


# ---------------------------------------------------------------- creating

def _slot_taken(db: Session, charger: Charger, start: datetime, blocks: int, now: datetime, message: str) -> AppError:
    db.rollback()
    found = alternatives.build(db, charger, start, blocks, now)
    return AppError(409, "SLOT_TAKEN", message, {"alternatives": found.model_dump(mode="json")})


def create_hold(
    db: Session, user_id: UUID, charger_id: UUID, start: datetime, blocks: int, vehicle_id: UUID | None, now: datetime
) -> BookingOut:
    """Hold a slot for 5 minutes while the driver pays the booking fee."""
    start = as_utc(start)
    if not is_slot_aligned(start):
        raise AppError(422, "SLOT_NOT_ALIGNED", "Slots start on the hour or the half hour.")
    if start <= now:
        raise AppError(422, "START_IN_PAST", "That slot has already started.")
    if start >= now + timedelta(days=BOOKING_RULES.max_days_ahead):
        raise AppError(422, "START_TOO_FAR", f"You can book up to {BOOKING_RULES.max_days_ahead} days ahead.")
    if not BOOKING_RULES.min_blocks_per_booking <= blocks <= BOOKING_RULES.max_blocks_per_booking:
        raise AppError(422, "INVALID_BLOCKS", f"Book {BOOKING_RULES.min_blocks_per_booking} to {BOOKING_RULES.max_blocks_per_booking} blocks.")
    end = start + blocks * SLOT

    charger = _charger_for_booking(db, charger_id)
    run_due_jobs(db, now, charger.station_id)  # lazy checks before looking at what is free
    _check_vehicle(db, user_id, vehicle_id, charger)

    booking = None
    for attempt in (1, 2):
        try:
            expire_stale_holds(db, now, charger_id=charger_id, user_id=user_id)  # lazy expiry, same transaction
            if _active_hold(db, user_id, now):
                raise _active_hold_error(db, user_id, now)
            _check_no_dues(db, user_id)

            state_machine.check(None, "HELD", "APP")
            state_machine.set_actor(db, "USER", "Booked in the app")
            booking = Booking(
                user_id=user_id, charger_id=charger_id, vehicle_id=vehicle_id, source="APP", status="HELD",
                time_range=Range(start, end, bounds="[)"),
                hold_expires_at=now + timedelta(minutes=BOOKING_RULES.payment_hold_minutes),
                booking_fee=BOOKING_RULES.booking_fee_inr,
            )
            db.add(booking)
            db.flush()  # the database accepts or refuses the slot here
            db.commit()
            break
        except AppError:
            db.rollback()
            raise
        except DBAPIError as exc:
            code = sqlstate(exc)
            if code == EXCLUSION_VIOLATION:
                raise _slot_taken(db, charger, start, blocks, now, "This slot was just taken.") from exc
            if code == UNIQUE_VIOLATION and HOLD_INDEX in str(exc):
                db.rollback()
                raise _active_hold_error(db, user_id, now) from exc
            if code == DEADLOCK and attempt == 1:
                db.rollback()  # two bookings crossed: try once more; the retry meets a clean 23P01
                continue
            if code == DEADLOCK:
                raise _slot_taken(db, charger, start, blocks, now, "This slot was just taken.") from exc
            db.rollback()
            raise
    return get_booking(db, user_id, booking.booking_id, now)


def create_instant(db: Session, user_id: UUID, charger_id: UUID, vehicle_id: UUID | None, now: datetime) -> InstantBookingOut:
    """"Charge now": from this moment until the next booking (minus a buffer) or 2 hours. No fee."""
    charger = _charger_for_booking(db, charger_id)
    run_due_jobs(db, now, charger.station_id)
    db.refresh(charger)  # the jobs may have changed its status
    # RESERVED only means a booking is about to start (the lock begins 15 minutes ahead); whether there is
    # room before it is decided below. Anything else (charging, broken) is busy.
    if charger.status not in ("AVAILABLE", "RESERVED"):
        raise AppError(409, "CHARGER_BUSY", "This charger is in use right now.")
    _check_vehicle(db, user_id, vehicle_id, charger)

    window: tuple[datetime, datetime] | None = None
    booking = None
    code = ""
    for attempt in (1, 2):
        try:
            expire_stale_holds(db, now, charger_id=charger_id)
            _check_no_dues(db, user_id)

            if db.scalar(
                select(func.count()).select_from(Booking).where(
                    Booking.charger_id == charger_id, occupies_charger(now), Booking.time_range.contains(now)
                )
            ):
                raise AppError(409, "CHARGER_BUSY", "This charger is booked right now.")
            next_start = db.scalar(
                select(func.min(func.lower(Booking.time_range))).where(
                    Booking.charger_id == charger_id, occupies_charger(now), func.lower(Booking.time_range) > now
                )
            )
            window = instant_window(now, next_start)
            if window is None:
                raise AppError(409, "NO_ROOM_FOR_INSTANT", "The next booking starts too soon to start charging now.")
            start, end = window

            state_machine.check(None, "CONFIRMED", "INSTANT")
            state_machine.set_actor(db, "USER", "Charge now")
            code, digest = otp.generate(taken_code_hashes(db, charger.station_id, start))
            booking = Booking(
                user_id=user_id, charger_id=charger_id, vehicle_id=vehicle_id, source="INSTANT", status="CONFIRMED",
                time_range=Range(start, end, bounds="[)"), otp_hash=digest, booking_fee=0,
            )
            db.add(booking)
            db.flush()
            db.commit()
            break
        except AppError:
            db.rollback()
            raise
        except DBAPIError as exc:
            code_ = sqlstate(exc)
            if code_ == DEADLOCK and attempt == 1:
                db.rollback()
                continue
            if code_ in (EXCLUSION_VIOLATION, DEADLOCK):
                blocks = blocks_in(*window) if window else 1
                raise _slot_taken(db, charger, now, blocks, now, "Someone just booked this charger.") from exc
            db.rollback()
            raise
    out = get_booking(db, user_id, booking.booking_id, now)
    return InstantBookingOut(**out.model_dump(), otp=code)


# ---------------------------------------------------------------- codes

def show_new_code(db: Session, user_id: UUID, booking_id: UUID, now: datetime) -> OtpOut:
    """Issue a new one-time code for a confirmed booking. The old code stops working."""
    booking = get_owned(db, user_id, booking_id, lock=True)
    status = effective_status(booking, now)
    opens, closes = otp.window(booking.start)
    if status != "CONFIRMED":
        raise AppError(409, "NO_CODE_FOR_STATUS", f"A {status.lower().replace('_', ' ')} booking has no code to show.")
    if booking.otp_used_at is not None:
        raise AppError(409, "CODE_ALREADY_USED", "The code for this booking was already used.")
    if now > closes:
        raise AppError(409, "CODE_WINDOW_ENDED", "The time to start this booking has passed.")
    code = issue_code(db, booking)
    db.commit()
    return OtpOut(booking_id=booking.booking_id, otp=code, valid_from=opens, valid_until=closes)


# ---------------------------------------------------------------- cancelling

def _refund_for(booking: Booking, payment: Payment | None, status: str, now: datetime) -> tuple[Decimal, int, str, Decimal]:
    """(refund, percent, reason, fee_paid) if the booking were cancelled right now."""
    paid = fee_paid_amount(payment)
    if status == "HELD":
        return Decimal("0.00"), 0, "You haven't paid yet, so nothing is charged.", paid
    if paid == 0:
        return Decimal("0.00"), 0, "No booking fee was paid for this booking, so there is nothing to refund.", paid
    refund = refunds.refund_for(now, booking.start, paid)
    return refund.amount, refund.percent, refund.reason, paid


def _cancellable(booking: Booking, now: datetime) -> str:
    status = effective_status(booking, now)
    if status not in ("HELD", "CONFIRMED"):
        raise AppError(409, "CANNOT_CANCEL", f"A {status.lower().replace('_', ' ')} booking can't be cancelled.")
    return status


def cancel_preview(db: Session, user_id: UUID, booking_id: UUID, now: datetime) -> RefundPreview:
    booking = get_owned(db, user_id, booking_id)
    status = _cancellable(booking, now)
    amount, percent, reason, paid = _refund_for(booking, booking_payment(db, booking_id), status, now)
    return RefundPreview(booking_id=booking_id, fee_paid=float(paid), refund_amount=float(amount), percent=percent, reason=reason)


def cancel(db: Session, user_id: UUID, booking_id: UUID, now: datetime) -> RefundPreview:
    """Cancel a held or confirmed booking. A confirmed one gets the refund its timing earns."""
    booking = get_owned(db, user_id, booking_id, lock=True)
    status = _cancellable(booking, now)
    payment = booking_payment(db, booking_id)
    amount, percent, reason, paid = _refund_for(booking, payment, status, now)

    state_machine.transition(
        db, booking, "CANCELLED", "USER", "Cancelled by the user" if status == "CONFIRMED" else "Cancelled before paying"
    )
    booking.cancelled_at = now
    booking.cancel_reason = reason
    booking.refund_amount = amount
    if payment is not None and amount > 0:
        # Test mode: the refund is calculated and recorded, not sent as real money.
        payment.refunded_amount = amount
        payment.status = "REFUNDED" if amount >= Decimal(payment.amount) else "PARTIALLY_REFUNDED"
    db.commit()
    return RefundPreview(booking_id=booking_id, fee_paid=float(paid), refund_amount=float(amount), percent=percent, reason=reason)
