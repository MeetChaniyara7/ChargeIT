"""The booking state machine: allowed moves work, everything else is refused (in Python AND by the database)."""

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.errors import AppError
from app.features.bookings import state_machine
from app.features.bookings.models import Booking
from app.features.bookings.state_machine import TRANSITIONS, is_allowed
from tests.conftest import needs_db
from tests.factories import make_booking, make_charger, make_station

STATUSES = ["HELD", "CONFIRMED", "ACTIVE", "COMPLETED", "EXPIRED", "CANCELLED", "NO_SHOW"]
SOURCES = ["APP", "INSTANT", "WALK_IN"]


def expected(from_status, to_status, source) -> bool:
    return any(f == from_status and t == to_status and s in (None, source) for f, t, s in TRANSITIONS)


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("from_status,to_status", list(itertools.product([None, *STATUSES], STATUSES)))
def test_every_pair_is_allowed_or_refused_as_the_table_says(from_status, to_status, source):
    assert is_allowed(from_status, to_status, source) is expected(from_status, to_status, source)
    if expected(from_status, to_status, source):
        state_machine.check(from_status, to_status, source)  # no error
    else:
        with pytest.raises(AppError) as error:
            state_machine.check(from_status, to_status, source)
        assert error.value.code == "ILLEGAL_STATUS_CHANGE"


def test_the_documented_paths():
    assert is_allowed(None, "HELD", "APP") and is_allowed(None, "CONFIRMED", "INSTANT") and is_allowed(None, "HELD", "WALK_IN")
    assert is_allowed("HELD", "CONFIRMED", "APP") and not is_allowed("HELD", "CONFIRMED", "INSTANT")
    assert is_allowed("HELD", "ACTIVE", "WALK_IN") and not is_allowed("HELD", "ACTIVE", "APP")
    for done in ("COMPLETED", "EXPIRED", "CANCELLED", "NO_SHOW"):
        assert not any(is_allowed(done, other, s) for other in STATUSES for s in SOURCES)  # final states stay final


def test_unknown_actor_is_a_programming_error():
    with pytest.raises(ValueError):
        state_machine.set_actor(None, "ROBOT")


@needs_db
def test_python_table_is_identical_to_the_database_table(db):
    rows = db.execute(text("SELECT from_status, to_status, source FROM allowed_booking_transitions")).all()
    assert {tuple(r) for r in rows} == set(TRANSITIONS)


def _booking(db, status="CONFIRMED"):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    hold = start if status == "HELD" else None
    booking_id = make_booking(db, make_charger(db, make_station(db)), start, start + timedelta(hours=1), status=status, hold_expires_at=hold)
    return booking_id, db.get(Booking, booking_id)


@needs_db
def test_transition_changes_status_and_records_who_and_why(db):
    booking_id, booking = _booking(db, "HELD")
    state_machine.transition(db, booking, "CANCELLED", "USER", "Changed my mind")
    assert booking.status == "CANCELLED"
    event = db.execute(
        text("SELECT from_status, to_status, actor, reason FROM booking_events WHERE booking_id = :b ORDER BY event_id DESC LIMIT 1"),
        {"b": booking_id},
    ).one()
    assert tuple(event) == ("HELD", "CANCELLED", "USER", "Changed my mind")


@needs_db
def test_illegal_change_is_refused_by_python_before_it_reaches_the_database(db):
    _, booking = _booking(db)  # CONFIRMED (instant)
    with pytest.raises(AppError):
        state_machine.transition(db, booking, "HELD", "SYSTEM")
    assert booking.status == "CONFIRMED"


@needs_db
@pytest.mark.parametrize("target", ["HELD", "EXPIRED", "COMPLETED"])
def test_the_database_refuses_illegal_changes_even_without_python(db, target):
    """A job or a person editing SQL by hand cannot make an illegal change either."""
    booking_id, _ = _booking(db)  # CONFIRMED can only go to ACTIVE, NO_SHOW or CANCELLED
    with pytest.raises(DBAPIError):
        with db.begin_nested():
            db.execute(text("UPDATE bookings SET status = :s WHERE booking_id = :b"), {"s": target, "b": booking_id})
