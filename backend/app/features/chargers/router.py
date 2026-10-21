"""Admin tools for the demo: simulate charger events, and start charging the way the kiosk will."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import require_admin
from app.features.chargers import service
from app.features.charging import service as charging
from app.features.charging.schemas import StartedSession

router = APIRouter(prefix="/api/admin", tags=["Admin: simulator"], dependencies=[Depends(require_admin)])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SimulateRequest(BaseModel):
    event: Literal["EXTERNAL_START", "EXTERNAL_STOP", "FAULT", "RECOVER", "UNPLUG"]


class SimulateResult(BaseModel):
    accepted: bool
    status: str  # the charger's status afterwards
    reason: str | None = None  # why it was refused
    session_id: UUID | None = None


@router.post("/chargers/{charger_id}/simulate", response_model=SimulateResult)
def simulate_charger_event(charger_id: UUID, body: SimulateRequest, db: Session = Depends(get_db)):
    """Make a charger behave like a real one: an outside start (refused while it is reserved), a stop,
    an unplug, a fault or a recovery. A refusal is a normal answer (accepted = false), not an error."""
    return service.simulate(db, charger_id, body.event, _now())


@router.post("/bookings/{booking_id}/start", response_model=StartedSession)
def start_booking_session(booking_id: UUID, db: Session = Depends(get_db)):
    """Demo stand-in for the kiosk: start charging for a confirmed booking as if its code was typed."""
    session = charging.start_session(db, booking_id, _now(), actor="ADMIN")
    return StartedSession(session_id=session.session_id, booking_id=session.booking_id, charger_id=session.charger_id)
