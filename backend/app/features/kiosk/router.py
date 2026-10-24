"""Endpoints the station kiosk tablet calls. Every one needs the X-Device-Key header and is limited to the device's own station."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.kiosk import service, stop, walkin
from app.features.kiosk.dependencies import get_current_device
from app.features.kiosk.models import StationDevice
from app.features.kiosk.schemas import KioskStatus, OtpStartOut, OtpStartRequest, WalkInCreate, WalkInOut, WalkInStop, WalkInStopOut
from app.features.payments.gateway import Gateway, get_gateway

router = APIRouter(prefix="/api/kiosk", tags=["Kiosk"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/status", response_model=KioskStatus)
def kiosk_status(device: StationDevice = Depends(get_current_device), db: Session = Depends(get_db)):
    """The status board: every charger's state, progress and free-until time. No names, phone numbers or bills.
    The setup screen also calls this to check a pasted key."""
    return service.status(db, device, _now())


@router.post("/otp-start", response_model=OtpStartOut)
def otp_start(body: OtpStartRequest, device: StationDevice = Depends(get_current_device), db: Session = Depends(get_db)):
    """Start the charger of the booking this code belongs to. 5 wrong tries in a row: 2 minutes' wait (429 OTP_COOLDOWN)."""
    return service.otp_start(db, device, body.otp, _now())


@router.post("/walk-ins", response_model=WalkInOut, status_code=201)
def create_walk_in(
    body: WalkInCreate, device: StationDevice = Depends(get_current_device), db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_gateway),
):
    """Take a free charger without a booking: holds it for 3 minutes and returns the payment link to show as a QR."""
    return walkin.create(db, device, body, gateway, _now())


@router.get("/walk-ins/{walk_in_id}", response_model=WalkInOut)
def get_walk_in(
    walk_in_id: UUID, device: StationDevice = Depends(get_current_device), db: Session = Depends(get_db),
    gateway: Gateway = Depends(get_gateway),
):
    """Has the walk-in paid yet? Poll this while the QR is on screen."""
    return walkin.get(db, device, walk_in_id, gateway, _now())


@router.post("/walk-ins/{walk_in_id}/cancel", response_model=WalkInOut)
def cancel_walk_in(walk_in_id: UUID, device: StationDevice = Depends(get_current_device), db: Session = Depends(get_db)):
    """Back out of the QR screen: the charger is free again at once."""
    return walkin.cancel(db, device, walk_in_id, _now())


@router.post("/walk-ins/stop", response_model=WalkInStopOut)
def stop_walk_in(body: WalkInStop, device: StationDevice = Depends(get_current_device), db: Session = Depends(get_db)):
    """Stop a walk-in early with the stop code it was given. The energy used is billed; the unused money is recorded as a refund."""
    return stop.stop_walk_in(db, device, body.code, _now())
