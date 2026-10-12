"""Booking endpoints. Everything here needs a signed-in user and only ever shows that user's own bookings."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.bookings import service
from app.features.bookings.schemas import (
    BookingCreate, BookingOut, DuesOut, InstantBookingOut, InstantCreate, OtpOut, RefundPreview, SlotTakenResponse,
)

router = APIRouter(prefix="/api", tags=["Bookings"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post(
    "/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED,
    responses={409: {"model": SlotTakenResponse, "description": "SLOT_TAKEN (with alternatives), ACTIVE_HOLD_EXISTS or UNPAID_BILL"}},
)
def create_booking(body: BookingCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Hold a slot for 5 minutes. Pay the fee in that time (POST /api/payments/orders) to confirm it."""
    return service.create_hold(db, user.user_id, body.charger_id, body.start, body.blocks, body.vehicle_id, _now())


@router.post(
    "/bookings/instant", response_model=InstantBookingOut, status_code=status.HTTP_201_CREATED,
    responses={409: {"model": SlotTakenResponse, "description": "CHARGER_BUSY, NO_ROOM_FOR_INSTANT, UNPAID_BILL or SLOT_TAKEN (with alternatives)"}},
)
def create_instant_booking(body: InstantCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """"Charge now" on a free charger: no fee, confirmed at once, the code is in this response (once)."""
    return service.create_instant(db, user.user_id, body.charger_id, body.vehicle_id, _now())


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.get_booking(db, user.user_id, booking_id, _now())


@router.post("/bookings/{booking_id}/otp", response_model=OtpOut)
def show_new_code(booking_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A new one-time code. The old one stops working."""
    return service.show_new_code(db, user.user_id, booking_id, _now())


@router.get("/bookings/{booking_id}/cancel-preview", response_model=RefundPreview)
def cancel_preview(booking_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """What you would get back if you cancelled right now (nothing changes)."""
    return service.cancel_preview(db, user.user_id, booking_id, _now())


@router.post("/bookings/{booking_id}/cancel", response_model=RefundPreview)
def cancel_booking(booking_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.cancel(db, user.user_id, booking_id, _now())


@router.get("/me/bookings", response_model=list[BookingOut])
def my_bookings(
    scope: Literal["upcoming", "past"] = Query("upcoming"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.my_bookings(db, user.user_id, scope, _now())


@router.get("/me/dues", response_model=DuesOut)
def my_dues(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Unpaid energy bills. While there are any, new bookings are refused (UNPAID_BILL)."""
    return service.unpaid_bills(db, user.user_id)
