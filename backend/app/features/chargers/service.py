"""The charger simulator: pretend a charger reports the events a real OCPP charger would.

We cannot connect to real chargers, so the admin can make these happen (docs/architecture.md 7.4).
The rules live in the database (migration 011, `simulate_charger_event`): a charger's status changes
only through these events, every one is logged in charger_events, and a reserved charger refuses an
outside start just as a real one would.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.errors import AppError

EVENTS = ("EXTERNAL_START", "EXTERNAL_STOP", "FAULT", "RECOVER", "UNPLUG")

NO_DATA_FOUND = "P0002"


def simulate(db: Session, charger_id: UUID, event: str, now: datetime) -> dict:
    """Makes one event happen on a charger. Returns {accepted, status, reason?, session_id?}."""
    if event not in EVENTS:
        raise AppError(422, "UNKNOWN_EVENT", f"Event must be one of: {', '.join(EVENTS)}.")
    try:
        result = db.execute(
            text("SELECT simulate_charger_event(CAST(:c AS uuid), :e, CAST(:now AS timestamptz))"),
            {"c": charger_id, "e": event, "now": now},
        ).scalar_one()
        db.commit()
    except DBAPIError as exc:
        db.rollback()
        if getattr(getattr(exc, "orig", None), "sqlstate", None) == NO_DATA_FOUND:
            raise AppError(404, "CHARGER_NOT_FOUND", "Charger not found.") from exc
        raise
    return result
