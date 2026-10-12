"""The ONLY way code changes a booking's status.

The table below is identical to `allowed_booking_transitions` in the database
(database/migrations/004_bookings.sql), which a trigger enforces too: a test compares
the two, so they cannot drift. Checking here first gives a clear error message; the
database check is the safety net for anything that bypasses this module.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError

# (from_status, to_status, source). None means "any source"; from None means "a new booking".
TRANSITIONS: frozenset[tuple[str | None, str, str | None]] = frozenset(
    {
        (None, "HELD", "APP"),
        (None, "CONFIRMED", "INSTANT"),
        (None, "HELD", "WALK_IN"),
        ("HELD", "CONFIRMED", "APP"),
        ("HELD", "ACTIVE", "WALK_IN"),
        ("HELD", "EXPIRED", None),
        ("HELD", "CANCELLED", None),
        ("CONFIRMED", "ACTIVE", None),
        ("CONFIRMED", "NO_SHOW", None),
        ("CONFIRMED", "CANCELLED", None),
        ("ACTIVE", "COMPLETED", None),
    }
)

ACTORS = ("USER", "DEVICE", "SYSTEM", "ADMIN")


def is_allowed(from_status: str | None, to_status: str, source: str) -> bool:
    return any(f == from_status and t == to_status and s in (None, source) for f, t, s in TRANSITIONS)


def check(from_status: str | None, to_status: str, source: str) -> None:
    if not is_allowed(from_status, to_status, source):
        raise AppError(
            409, "ILLEGAL_STATUS_CHANGE",
            f"A {source} booking cannot go from {from_status or '(new)'} to {to_status}.",
        )


def set_actor(db: Session, actor: str, reason: str | None = None) -> None:
    """Tell the database trigger who is making the change and why (for booking_events).

    Applies to the current transaction only.
    """
    if actor not in ACTORS:
        raise ValueError(f"Unknown actor {actor!r}")
    db.execute(select(func.set_config("chargespot.actor", actor, True), func.set_config("chargespot.reason", reason or "", True)))


def transition(db: Session, booking, new_status: str, actor: str, reason: str | None = None) -> None:
    """Move an existing booking to a new status (flushes, does not commit)."""
    check(booking.status, new_status, booking.source)
    set_actor(db, actor, reason)
    booking.status = new_status
    db.flush()
