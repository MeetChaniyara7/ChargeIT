"""Walk-ins: someone with no booking takes a free charger and pays first with a QR code.

The order is the point (docs/architecture.md section 7.3): pay first, then charge, so nobody can drive
away without paying and no staff are needed.

1. The kiosk asks for a charger and an amount. The server decides the time window (the same rule as
   "Charge now"), makes a WALK_IN booking in status HELD for 3 minutes and creates a Razorpay Payment
   Link. The no-overlap rule of the database protects the charger exactly like any other booking.
2. The person scans the QR and pays on their phone. Razorpay tells us (webhook `payment_link.paid`) or,
   while no webhook is registered, the kiosk's own polling asks Razorpay. Either way the payment counts only
   once Razorpay itself says it is paid, and both paths end in `confirm_payment`, which runs once.
3. The booking goes HELD -> ACTIVE, a session starts with `prepaid_amount`, the charger starts.
4. When the session ends, the SQL function `finish_session` bills the energy used and records the
   leftover as a refund on the payment.
If the 3 minutes run out first the booking EXPIRES and the charger is free again. A payment that
arrives after that is refunded in full (recorded).
"""

import time
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config import BOOKING_RULES, CHARGING_RULES
from app.core.errors import AppError
from app.features.availability.occupancy import occupies_charger
from app.features.bookings import service as bookings, state_machine
from app.features.bookings.instant import instant_window
from app.features.bookings.models import Booking
from app.features.charging.models import ChargingSession
from app.features.jobs.lazy import run_due_jobs
from app.features.kiosk import service as kiosk
from app.features.kiosk.models import StationDevice
from app.features.kiosk.schemas import WalkInCreate, WalkInOut
from app.features.payments.gateway import Gateway
from app.features.payments.models import Payment
from app.features.stations.models import Charger

POLL_PROVIDER_EVERY_SECONDS = 3.0
_last_asked: dict[str, float] = {}  # payment link id -> when we last asked Razorpay (so a busy kiosk does not flood it)


def _out(booking: Booking, charger: Charger, payment: Payment | None, now: datetime, url: str | None, session_id: UUID | None) -> WalkInOut:
    effective = bookings.effective_status(booking, now)
    if effective == "HELD":
        status = "WAITING_FOR_PAYMENT"
    elif effective in ("ACTIVE", "COMPLETED"):
        status = "PAID"
    elif effective == "CANCELLED":
        status = "CANCELLED"
    else:
        status = "EXPIRED"
    expires = booking.hold_expires_at or booking.start
    return WalkInOut(
        walk_in_id=booking.booking_id, status=status, charger_id=charger.charger_id, charger_label=charger.label,
        amount=float(payment.amount) if payment else 0, payment_url=url if status == "WAITING_FOR_PAYMENT" else None,
        expires_at=expires, server_time=now, seconds_left=max(0, int((expires - now).total_seconds())) if status == "WAITING_FOR_PAYMENT" else 0,
        session_id=session_id, refunded=float(payment.refunded_amount) if payment else 0,
    )


def _payment_of(db: Session, booking_id: UUID) -> Payment | None:
    return db.scalar(select(Payment).where(Payment.booking_id == booking_id, Payment.purpose == "WALKIN_PREPAID"))


def _load(db: Session, device: StationDevice, walk_in_id: UUID, *, lock: bool = False) -> tuple[Booking, Charger]:
    query = (
        select(Booking, Charger)
        .join(Charger, Charger.charger_id == Booking.charger_id)
        .where(Booking.booking_id == walk_in_id, Booking.source == "WALK_IN", Charger.station_id == device.station_id)
    )
    if lock:
        query = query.with_for_update(of=Booking)
    row = db.execute(query).first()
    if row is None:  # also what a tablet from another station gets: it must not learn the id exists
        raise AppError(404, "WALK_IN_NOT_FOUND", "Walk-in not found.")
    return row[0], row[1]


# ---------------------------------------------------------------- starting one

def create(db: Session, device: StationDevice, body: WalkInCreate, gateway: Gateway, now: datetime) -> WalkInOut:
    if (body.amount is None) == (not body.until_next):
        raise AppError(400, "INVALID_AMOUNT", "Choose one amount, or \"until the next booking\".")
    if body.amount is not None and body.amount not in BOOKING_RULES.walkin_amounts_inr:
        raise AppError(400, "INVALID_AMOUNT", f"Choose one of: {', '.join('₹' + str(a) for a in BOOKING_RULES.walkin_amounts_inr)}.")

    charger = db.scalar(
        select(Charger).where(Charger.charger_id == body.charger_id, Charger.station_id == device.station_id).with_for_update()
    )
    if charger is None:  # a charger of another station looks exactly like one that does not exist
        raise AppError(404, "CHARGER_NOT_FOUND", "Charger not found at this station.")
    run_due_jobs(db, now, charger.station_id)
    db.refresh(charger)
    if charger.status in ("FAULTED", "OUT_OF_SERVICE"):
        raise AppError(409, "CHARGER_UNAVAILABLE", "This charger is out of service.")
    if charger.status not in ("AVAILABLE", "RESERVED"):
        raise AppError(409, "CHARGER_BUSY", "This charger is in use.")
    if charger.price_per_kwh is None or Decimal(str(charger.price_per_kwh)) <= 0 or not charger.power_kw:
        raise AppError(409, "PRICE_UNKNOWN", "This charger cannot take walk-ins: its price or power is not known.")

    booking = None
    window = None
    for attempt in (1, 2):
        try:
            bookings.expire_stale_holds(db, now, charger_id=charger.charger_id)
            if db.scalar(
                select(Booking.booking_id).where(Booking.charger_id == charger.charger_id, occupies_charger(now), Booking.time_range.contains(now)).limit(1)
            ):
                raise AppError(409, "CHARGER_BUSY", "This charger is booked right now.")
            next_start = db.scalar(
                select(func.min(func.lower(Booking.time_range))).where(
                    Booking.charger_id == charger.charger_id, occupies_charger(now), func.lower(Booking.time_range) > now
                )
            )
            window = instant_window(now, next_start)
            if window is None:
                raise AppError(409, "NO_ROOM_FOR_WALK_IN", "The next booking starts too soon for a walk-in.")
            amount = body.amount if body.amount is not None else kiosk.until_next_amount(charger, *window)

            state_machine.check(None, "HELD", "WALK_IN")
            state_machine.set_actor(db, "DEVICE", "Walk-in at the kiosk")
            booking = Booking(
                charger_id=charger.charger_id, source="WALK_IN", status="HELD", time_range=Range(window[0], window[1], bounds="[)"),
                hold_expires_at=now + timedelta(minutes=BOOKING_RULES.walkin_qr_hold_minutes), booking_fee=0,
            )
            db.add(booking)
            db.flush()
            db.commit()
            break
        except AppError:
            db.rollback()
            raise
        except DBAPIError as exc:
            code = bookings.sqlstate(exc)
            db.rollback()
            if code == bookings.DEADLOCK and attempt == 1:
                continue
            if code in (bookings.EXCLUSION_VIOLATION, bookings.DEADLOCK):
                raise AppError(409, "CHARGER_BUSY", "Someone just took this charger.") from exc
            raise

    try:
        link_id, url = gateway.create_payment_link(
            amount * 100, reference_id=str(booking.booking_id),
            description=f"ChargeSpot walk-in charging, charger {charger.label}",
            notes={"purpose": "WALKIN_PREPAID", "booking_id": str(booking.booking_id)},
        )
    except AppError:
        _free(db, booking.booking_id, "The payment link could not be created")
        raise
    payment = Payment(
        booking_id=booking.booking_id, purpose="WALKIN_PREPAID", provider="razorpay", provider_order_id=link_id,
        amount=Decimal(amount), currency="INR", status="CREATED",
    )
    db.add(payment)
    db.commit()
    db.refresh(booking)
    return _out(booking, charger, payment, now, url, None)


def _free(db: Session, booking_id: UUID, reason: str) -> None:
    """Give the charger back at once (the QR will never be shown)."""
    booking = db.get(Booking, booking_id)
    if booking is not None and booking.status == "HELD":
        state_machine.transition(db, booking, "CANCELLED", "DEVICE", reason)
        db.commit()


# ---------------------------------------------------------------- watching it

def get(db: Session, device: StationDevice, walk_in_id: UUID, gateway: Gateway, now: datetime) -> WalkInOut:
    """The kiosk asks every couple of seconds. While we wait for the money, ask Razorpay too (the webhook is the backup, not the only way)."""
    booking, charger = _load(db, device, walk_in_id)
    payment = _payment_of(db, walk_in_id)
    if payment is not None and payment.status == "CREATED" and bookings.effective_status(booking, now) == "HELD":
        _ask_razorpay(db, payment, gateway, now)
    run_due_jobs(db, now, charger.station_id)
    booking, charger = _load(db, device, walk_in_id)
    db.refresh(booking)
    payment = _payment_of(db, walk_in_id)
    if payment is not None:
        db.refresh(payment)
    session_id = db.scalar(select(ChargingSession.session_id).where(ChargingSession.booking_id == walk_in_id))
    return _out(booking, charger, payment, now, None, session_id)


def _ask_razorpay(db: Session, payment: Payment, gateway: Gateway, now: datetime) -> None:
    link_id = payment.provider_order_id
    if time.monotonic() - _last_asked.get(link_id, 0.0) < POLL_PROVIDER_EVERY_SECONDS:
        return
    _last_asked[link_id] = time.monotonic()
    try:
        status, payment_id = gateway.payment_link_status(link_id)
    except AppError:
        return  # the next poll tries again
    if status == "paid" and payment_id:
        locked = db.scalar(select(Payment).where(Payment.payment_id == payment.payment_id).with_for_update())
        confirm_payment(db, locked, payment_id, now, actor="DEVICE")
        db.commit()


def cancel(db: Session, device: StationDevice, walk_in_id: UUID, now: datetime) -> WalkInOut:
    """"Cancel" on the QR screen: the charger is free again straight away."""
    booking, charger = _load(db, device, walk_in_id, lock=True)
    if booking.status == "HELD":
        state_machine.transition(db, booking, "CANCELLED", "DEVICE", "Cancelled at the kiosk")
        booking.cancelled_at = now
        db.commit()
    return _out(booking, charger, _payment_of(db, walk_in_id), now, None, None)


# ---------------------------------------------------------------- the money arrived

def _refund_in_full(payment: Payment, booking: Booking) -> str:
    amount = Decimal(payment.amount)
    payment.status = "REFUNDED"
    payment.refunded_amount = amount
    booking.refund_amount = amount
    return "REFUNDED"


def confirm_payment(db: Session, payment: Payment, provider_payment_id: str, now: datetime, actor: str) -> str:
    """Razorpay says this walk-in's payment link was paid. Start charging. Safe to call twice.

    Returns STARTED, REFUNDED (too late, or the charger broke) or ALREADY.
    """
    booking = db.scalars(select(Booking).where(Booking.booking_id == payment.booking_id).with_for_update()).one()
    if payment.status != "CREATED":
        return "ALREADY"
    payment.provider_payment_id = provider_payment_id
    payment.status = "CAPTURED"

    if booking.status != "HELD":  # expired or cancelled while they were paying
        return _refund_in_full(payment, booking)
    charger = db.scalars(select(Charger).where(Charger.charger_id == booking.charger_id).with_for_update()).one()
    if charger.status not in ("AVAILABLE", "RESERVED"):  # it broke or got taken while they were paying
        state_machine.transition(db, booking, "EXPIRED", "SYSTEM", "The charger became unavailable before the payment arrived")
        return _refund_in_full(payment, booking)

    state_machine.transition(db, booking, "ACTIVE", actor, "Walk-in payment received")
    booking.hold_expires_at = None
    session = ChargingSession(
        booking_id=booking.booking_id, charger_id=charger.charger_id, source="WALK_IN", started_at=now,
        start_soc_percent=CHARGING_RULES.default_start_soc_percent, prepaid_amount=payment.amount,
    )
    db.add(session)
    db.flush()
    payment.session_id = session.session_id
    db.execute(
        text("SELECT apply_charger_event(CAST(:c AS uuid), 'SESSION_START', CAST('{}' AS jsonb), 'SYSTEM', CAST(:now AS timestamptz))"),
        {"c": charger.charger_id, "now": now},
    )
    db.flush()
    return "STARTED"
