"""The signed-in driver's charging sessions."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.charging import receipt, service
from app.features.charging.schemas import LiveSession, ReceiptOut
from app.features.payments import service as payments
from app.features.payments.gateway import Gateway, get_gateway
from app.features.payments.schemas import EnergyOrderOut, VerifyRequest

router = APIRouter(prefix="/api/me/sessions", tags=["Charging"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/active", response_model=LiveSession | None)
def active_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The session that is charging right now, or null. Powers the Charging tab and the app-bar pill."""
    return service.active_session(db, user.user_id, _now())


@router.get("/{session_id}", response_model=LiveSession)
def get_session(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Live values: energy, battery level, cost so far, time left. Only the owner can see a session."""
    return service.get_session(db, user.user_id, session_id, _now())


@router.post("/{session_id}/stop", response_model=LiveSession)
def stop_session(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Stop charging now. The bill is worked out up to this moment."""
    return service.stop_session(db, user.user_id, session_id, _now())


@router.post("/{session_id}/pay", response_model=EnergyOrderOut)
def pay_bill(
    session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db), gateway: Gateway = Depends(get_gateway)
):
    """The Razorpay order for this session's energy bill (the amount is the bill the server worked out)."""
    return payments.create_energy_order(db, user.user_id, session_id, gateway)


@router.post("/{session_id}/pay/verify", response_model=LiveSession)
def verify_bill(session_id: UUID, body: VerifyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check Razorpay's signature, mark the bill paid and return the updated session."""
    return payments.verify_energy(db, user.user_id, session_id, body, _now())


@router.get("/{session_id}/receipt", response_model=ReceiptOut)
def get_receipt(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The receipt for a finished session (DUE bills show as unpaid)."""
    return receipt.get_receipt(db, user.user_id, session_id, _now())
