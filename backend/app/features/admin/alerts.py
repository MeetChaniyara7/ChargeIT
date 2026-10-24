"""Raising an alert for the admin page, without ever making the thing that raised it fail."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.kiosk.models import AdminAlert

logger = logging.getLogger(__name__)


def raise_alert(
    db: Session, kind: str, message: str, details: dict | None = None, *, station_id: UUID | None = None,
    quiet_minutes: int = 10,
) -> bool:
    """Add an alert unless an unseen one of the same kind and message was raised in the last `quiet_minutes`
    (a flood of identical failures is one alert, not hundreds). Commits. Returns True if one was added."""
    try:
        now = datetime.now(timezone.utc)
        recent = db.scalar(
            select(func.count()).where(
                AdminAlert.kind == kind, AdminAlert.message == message, AdminAlert.resolved_at.is_(None),
                AdminAlert.created_at > now - timedelta(minutes=quiet_minutes),
            )
        )
        if recent:
            return False
        db.add(AdminAlert(kind=kind, message=message, details=details or {}, station_id=station_id, created_at=now))
        db.commit()
        return True
    except SQLAlchemyError:
        logger.exception("Could not record the %s alert", kind)
        db.rollback()
        return False
