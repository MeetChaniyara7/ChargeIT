"""The "lazy" checks: run the background jobs for one station right before answering.

pg_cron runs the jobs every minute (migration 012), but correctness never depends on that: before
the API shows availability, makes a booking or reads a charging session, it runs the same SQL
job functions for the station involved (docs/architecture.md section 6.2). So an expired hold, a
missed code, a session past its slot end, or a charger that is occupied at the start time is
dealt with the moment anyone looks, even if the job has not run yet.
"""

import logging
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_STATIONS = 5  # a list of bookings never needs more than this many stations checked


def run_due_jobs(db: Session, now: datetime, station_id: UUID | None = None) -> dict | None:
    """Runs all five jobs (for one station, or all of them) and commits. Returns what they did.

    It is a courtesy before a read, so it must never make the read fail: if the jobs hit a
    problem (say two requests asked at the same instant and one lost a lock), the error is logged,
    the attempt is undone and the read goes on with the data it has.
    """
    try:
        result = db.execute(
            text("SELECT run_due_jobs(CAST(:now AS timestamptz), CAST(:station AS uuid))"),
            {"now": now, "station": station_id},
        ).scalar_one()
        db.commit()
        return result
    except SQLAlchemyError:
        logger.exception("The lazy job check failed; carrying on without it")
        db.rollback()
        return None


def run_for_stations(db: Session, now: datetime, station_ids: Iterable[UUID]) -> None:
    for station_id in list(dict.fromkeys(station_ids))[:MAX_STATIONS]:
        run_due_jobs(db, now, station_id)
