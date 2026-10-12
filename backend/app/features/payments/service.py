"""Paying the booking fee: create the order, verify the result, handle the webhook.

Rules (docs/architecture.md section 8):
- Amounts are calculated here, on the server. The browser never sends one.
- A booking is CONFIRMED only after the payment's signature is verified (or a verified
  webhook says the payment was captured). The browser's word alone counts for nothing.
- Each webhook event is processed once, however many times Razorpay sends it.
- Verify and webhook can both arrive (or arrive late, or in either order): whichever comes
  second finds the payment already CAPTURED and changes nothing.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range, insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config import BOOKING_RULES, get_settings, require_setting
from app.core.errors import AppError
from app.features.bookings import otp, service as bookings, state_machine
from app.features.bookings.models import Booking
from app.features.payments.gateway import Gateway, verify_payment_signature, verify_webhook_signature
from app.features.payments.models import Payment, WebhookEvent
from app.features.payments.schemas import OrderOut, VerifyOut, VerifyRequest

# Checkout closes this many seconds before the hold would run out.
CHECKOUT_MARGIN_SECONDS = 15
MIN_CHECKOUT_SECONDS = 20


@dataclass
class Confirmation:
    outcome: str  # CONFIRMED | ALREADY_CONFIRMED | REFUNDED_LATE
    booking: Booking
    otp: str | None = None
    refund: Decimal = Decimal(0)


def _lock_booking(db: Session, booking_id: UUID) -> Booking:
    booking = db.scalars(
        select(Booking).options(bookings._loaders()).where(Booking.booking_id == booking_id).with_for_update(of=Booking)
    ).unique().first()
    if booking is None:  # cannot happen: payments.booking_id is a foreign key
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found.")
    return booking


def _lock_payment(db: Session, order_id: str) -> Payment | None:
    return db.scalar(select(Payment).where(Payment.provider_order_id == order_id).with_for_update())


# ---------------------------------------------------------------- creating the order

def create_order(db: Session, user_id: UUID, booking_id: UUID, gateway: Gateway, now: datetime) -> OrderOut:
    """The Razorpay order for a held booking's fee. Asking again returns the same order (a retry after a failed payment)."""
    booking = bookings.get_owned(db, user_id, booking_id, lock=True)
    status = bookings.effective_status(booking, now)
    if status == "EXPIRED":
        bookings.expire_if_stale(db, booking, now)
        raise AppError(409, "HOLD_EXPIRED", "Your hold ran out and the slot was released.")
    if status != "HELD" or booking.source != "APP":
        raise AppError(409, "BOOKING_NOT_PAYABLE", "This booking is not waiting for payment.")

    payment = db.scalar(
        select(Payment).where(Payment.booking_id == booking_id, Payment.purpose == "BOOKING_FEE", Payment.status == "CREATED")
    )
    if payment is None:
        amount = Decimal(booking.booking_fee)  # set by the server when the hold was made
        order_id = gateway.create_order(
            int(amount * 100), receipt=str(booking_id), notes={"purpose": "BOOKING_FEE", "booking_id": str(booking_id)}
        )
        payment = Payment(
            booking_id=booking_id, purpose="BOOKING_FEE", provider="razorpay", provider_order_id=order_id,
            amount=amount, currency="INR", status="CREATED",
        )
        db.add(payment)
        db.commit()

    remaining = int((booking.hold_expires_at - now).total_seconds())
    timeout = min(remaining, max(MIN_CHECKOUT_SECONDS, remaining - CHECKOUT_MARGIN_SECONDS))
    amount = Decimal(payment.amount)
    return OrderOut(
        booking_id=booking_id, order_id=payment.provider_order_id, amount=float(amount), amount_paise=int(amount * 100),
        currency=payment.currency, key_id=require_setting("razorpay_key_id"),
        hold_expires_at=booking.hold_expires_at, checkout_timeout_seconds=timeout,
    )


# ---------------------------------------------------------------- confirming

def _refund_in_full(payment: Payment, booking: Booking) -> Confirmation:
    amount = Decimal(payment.amount)
    payment.status = "REFUNDED"
    payment.refunded_amount = amount
    booking.refund_amount = amount
    return Confirmation("REFUNDED_LATE", booking, refund=amount)


def _rebook_expired(db: Session, payment: Payment, old: Booking, now: datetime) -> Confirmation | None:
    """A payment arrived after its hold expired. Take the same slot again if nobody else has it."""
    try:
        with db.begin_nested():  # if the slot is gone, only this attempt is undone
            state_machine.check(None, "HELD", "APP")
            state_machine.set_actor(db, "SYSTEM", "Payment arrived after the hold expired; slot was still free")
            new = Booking(
                user_id=old.user_id, charger_id=old.charger_id, vehicle_id=old.vehicle_id, source="APP", status="HELD",
                time_range=Range(old.start, old.end, bounds="[)"),
                hold_expires_at=now + timedelta(minutes=BOOKING_RULES.payment_hold_minutes), booking_fee=old.booking_fee,
            )
            db.add(new)
            db.flush()
            state_machine.transition(db, new, "CONFIRMED", "SYSTEM", "Booking fee paid (late payment)")
            new.hold_expires_at = None
            payment.booking_id = new.booking_id
            db.flush()
    except DBAPIError as exc:
        if bookings.sqlstate(exc) in (bookings.EXCLUSION_VIOLATION, bookings.UNIQUE_VIOLATION):
            return None  # someone took the slot (or the user started another hold)
        raise
    return Confirmation("CONFIRMED", new, otp=bookings.issue_code(db, new))


def confirm_payment(db: Session, payment: Payment, provider_payment_id: str, now: datetime, actor: str) -> Confirmation:
    """A verified payment: mark it captured and confirm the booking. Safe to call twice for one payment."""
    booking = _lock_booking(db, payment.booking_id)
    if payment.status != "CREATED":
        return Confirmation("ALREADY_CONFIRMED", booking, refund=Decimal(payment.refunded_amount))

    payment.provider_payment_id = provider_payment_id
    payment.status = "CAPTURED"
    window_open = now <= otp.window(booking.start)[1]  # after this the slot itself is over

    if booking.status == "HELD" and window_open:
        # Still held, even if the 5 minutes just ran out: nobody could take the slot meanwhile.
        state_machine.transition(db, booking, "CONFIRMED", actor, "Booking fee paid")
        booking.hold_expires_at = None
        return Confirmation("CONFIRMED", booking, otp=bookings.issue_code(db, booking))
    if booking.status == "EXPIRED" and window_open:
        rebooked = _rebook_expired(db, payment, booking, now)
        if rebooked:
            return rebooked
    if booking.status in ("HELD", "EXPIRED", "CANCELLED"):
        # Too late, or the slot is gone, or the driver had already backed out: give the fee back.
        if booking.status == "HELD":
            state_machine.transition(db, booking, "EXPIRED", "SYSTEM", "Payment arrived too late")
        return _refund_in_full(payment, booking)
    return Confirmation("ALREADY_CONFIRMED", booking)  # CONFIRMED already, or charging has started


_MESSAGES = {
    "CONFIRMED": "Payment received. Your slot is booked.",
    "ALREADY_CONFIRMED": "This payment was already processed.",
    "REFUNDED_LATE": "Your payment arrived after the hold ran out and the slot is no longer free, so the full fee is being refunded.",
}


def verify(db: Session, user_id: UUID, request: VerifyRequest, now: datetime) -> VerifyOut:
    """The browser says the payment went through. Believe it only if the signature is genuine."""
    if not verify_payment_signature(
        request.razorpay_order_id, request.razorpay_payment_id, request.razorpay_signature, require_setting("razorpay_key_secret")
    ):
        raise AppError(400, "INVALID_SIGNATURE", "The payment could not be verified.")
    payment = _lock_payment(db, request.razorpay_order_id)
    if payment is None:
        raise AppError(404, "PAYMENT_NOT_FOUND", "Payment not found.")
    if bookings.get_owned(db, user_id, payment.booking_id).booking_id != payment.booking_id:  # owner only
        raise AppError(404, "PAYMENT_NOT_FOUND", "Payment not found.")

    result = confirm_payment(db, payment, request.razorpay_payment_id, now, actor="USER")
    db.commit()
    booking = bookings.get_owned(db, user_id, result.booking.booking_id)
    return VerifyOut(
        outcome=result.outcome, booking=bookings.to_out(booking, bookings.booking_payment(db, booking.booking_id), now),
        otp=result.otp, refund_amount=float(result.refund), message=_MESSAGES[result.outcome],
    )


# ---------------------------------------------------------------- webhooks

def _event_ids(payload: dict) -> tuple[str | None, str | None]:
    """(order_id, payment_id) from a payment.* or order.* event."""
    entities = payload.get("payload", {})
    payment = entities.get("payment", {}).get("entity", {})
    order = entities.get("order", {}).get("entity", {})
    return payment.get("order_id") or order.get("id"), payment.get("id")


def handle_webhook(db: Session, body: bytes, signature: str, event_id: str | None, now: datetime) -> str:
    """Razorpay tells us about a payment. Verified, de-duplicated, and used only as a backup for /verify."""
    if not verify_webhook_signature(body, signature, require_setting("razorpay_webhook_secret")):
        raise AppError(400, "INVALID_SIGNATURE", "Invalid webhook signature.")
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise AppError(400, "INVALID_PAYLOAD", "The webhook body is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise AppError(400, "INVALID_PAYLOAD", "The webhook body is not a JSON object.")

    event_type = str(payload.get("event", ""))
    # Razorpay numbers every delivery of an event the same way, so a repeat is recognised.
    event_key = event_id or sha256(body).hexdigest()
    inserted = db.execute(
        pg_insert(WebhookEvent)
        .values(provider_event_id=event_key, event_type=event_type, payload=payload)
        .on_conflict_do_nothing()
        .returning(WebhookEvent.provider_event_id)
    ).first()
    if inserted is None:
        db.rollback()
        return "duplicate"

    status = "ignored"
    if event_type in ("payment.captured", "order.paid"):
        order_id, payment_id = _event_ids(payload)
        payment = _lock_payment(db, order_id) if order_id else None
        if payment is not None and payment_id:
            confirm_payment(db, payment, payment_id, now, actor="SYSTEM")
            status = "processed"
    db.execute(
        WebhookEvent.__table__.update().where(WebhookEvent.provider_event_id == event_key).values(processed_at=now)
    )
    db.commit()
    return status


def settings_ready() -> bool:
    """True when all the payment secrets are set (used by the health check and tests)."""
    s = get_settings()
    return bool(s.razorpay_key_id and s.razorpay_key_secret and s.razorpay_webhook_secret and s.otp_secret)
