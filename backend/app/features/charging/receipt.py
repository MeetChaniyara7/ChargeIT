"""The receipt for a finished charging session: what was delivered, the rate, the total and how it was paid."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.features.charging import service
from app.features.charging.schemas import ReceiptOut
from app.features.payments.models import Payment


def get_receipt(db: Session, user_id: UUID, session_id: UUID, now: datetime) -> ReceiptOut:
    session, booking, charger, station, _ = service._load_fresh(db, user_id, session_id, now)
    if session.ended_at is None:
        raise AppError(409, "SESSION_NOT_ENDED", "The receipt is ready when charging ends.")
    if session.bill_status is None:
        raise AppError(404, "NO_RECEIPT", "There is no bill for this session.")

    payment = db.scalar(
        select(Payment)
        .where(Payment.session_id == session_id, Payment.purpose == "ENERGY", Payment.status == "CAPTURED")
        .order_by(Payment.created_at.desc())
    )
    fee = db.scalar(
        select(Payment.amount).where(Payment.booking_id == booking.booking_id, Payment.purpose == "BOOKING_FEE", Payment.status.in_(("CAPTURED", "PARTIALLY_REFUNDED")))
    )
    return ReceiptOut(
        session_id=session.session_id,
        booking_id=session.booking_id,
        station_name=station.name,
        station_address=station.address,
        station_city=station.city,
        charger_label=charger.label,
        connector_type=charger.connector_type,
        power_kw=float(charger.power_kw) if charger.power_kw is not None else None,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_minutes=round(max((session.ended_at - session.started_at).total_seconds(), 0) / 60, 1),
        energy_kwh=float(session.energy_kwh),
        price_per_kwh=float(charger.price_per_kwh) if charger.price_per_kwh is not None else None,
        total=float(session.bill_amount or 0),
        bill_status=session.bill_status,
        paid_at=session.paid_at,
        payment_reference=payment.provider_payment_id if payment else None,
        booking_fee=float(Decimal(fee)) if fee is not None else None,
        source=session.source,
    )
