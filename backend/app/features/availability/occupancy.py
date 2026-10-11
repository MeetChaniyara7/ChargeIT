"""Which chargers are occupied, and when. The single source of truth for "is it free?".

Station search, the availability grid and recommendations all ask this module, so they
can never disagree about whether a charger is free.

Lazy expiry: a HELD booking whose hold time has passed counts as FREE straight away, even
if the background job that marks it EXPIRED hasn't run yet (docs/architecture.md 6.2).
"""

from collections.abc import Iterable
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session

from app.features.bookings.models import LIVE_STATUSES, Booking


def occupies_charger(now: datetime):
    """SQL condition: the booking is live and (if it is a hold) has not run out yet."""
    return and_(
        Booking.status.in_(LIVE_STATUSES),
        or_(Booking.status != "HELD", Booking.hold_expires_at.is_(None), Booking.hold_expires_at > now),
    )


def bookings_overlapping(
    db: Session, charger_ids: Iterable[UUID], start: datetime, end: datetime, now: datetime
) -> list[tuple[UUID, str, datetime, datetime]]:
    """Live bookings that overlap [start, end) on the given chargers, in ONE query.

    Returns (charger_id, status, booking_start, booking_end).
    """
    ids = list(charger_ids)
    if not ids:
        return []
    rows = db.execute(
        select(Booking.charger_id, Booking.status, Booking.time_range).where(
            Booking.charger_id.in_(ids),
            occupies_charger(now),
            Booking.time_range.overlaps(Range(start, end, bounds="[)")),
        )
    ).all()
    return [(charger_id, status, window.lower, window.upper) for charger_id, status, window in rows]


def busy_charger_ids(db: Session, charger_ids: Iterable[UUID], start: datetime, end: datetime, now: datetime) -> set[UUID]:
    """Chargers that have a live booking overlapping [start, end)."""
    return {row[0] for row in bookings_overlapping(db, charger_ids, start, end, now)}


def busy_right_now(db: Session, charger_ids: Iterable[UUID], now: datetime) -> set[UUID]:
    """Chargers with a live booking covering this very moment."""
    return busy_charger_ids(db, charger_ids, now, now + timedelta(microseconds=1), now)


# A charger in one of these physical states can't be used at all.
UNUSABLE_STATUSES = ("FAULTED", "OUT_OF_SERVICE")
