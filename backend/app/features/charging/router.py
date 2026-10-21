"""The signed-in driver's charging sessions."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.charging import service
from app.features.charging.schemas import LiveSession

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
