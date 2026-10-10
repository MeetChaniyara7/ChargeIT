"""The database itself must enforce the booking rules (docs/architecture.md 5.3 and 6.1)."""

import psycopg
import pytest
from psycopg import errors

from database.tests.conftest import make_booking, make_charger, make_user, slot


def test_overlapping_bookings_on_one_charger_are_rejected(db):
    charger, alice, bob = make_charger(db), make_user(db, "a@t.dev"), make_user(db, "b@t.dev")
    make_booking(db, charger, alice, slot(0, 60))           # 10:00-11:00
    with pytest.raises(errors.ExclusionViolation) as exc:   # SQLSTATE 23P01
        make_booking(db, charger, bob, slot(30, 60))         # 10:30-11:30 overlaps
    assert exc.value.sqlstate == "23P01"


def test_back_to_back_bookings_are_allowed(db):
    charger, alice, bob = make_charger(db), make_user(db, "a@t.dev"), make_user(db, "b@t.dev")
    make_booking(db, charger, alice, slot(0, 30))   # 10:00-10:30
    make_booking(db, charger, bob, slot(30, 30))    # 10:30-11:00 starts exactly when the first ends


def test_same_time_on_different_chargers_is_allowed(db):
    alice, bob = make_user(db, "a@t.dev"), make_user(db, "b@t.dev")
    make_booking(db, make_charger(db), alice, slot(0, 60))
    make_booking(db, make_charger(db), bob, slot(0, 60))


@pytest.mark.parametrize("final_status, path", [
    ("CANCELLED", ["CANCELLED"]),
    ("NO_SHOW", ["NO_SHOW"]),
    ("COMPLETED", ["ACTIVE", "COMPLETED"]),
])
def test_finished_bookings_free_the_slot(db, final_status, path):
    charger, alice, bob = make_charger(db), make_user(db, "a@t.dev"), make_user(db, "b@t.dev")
    first = make_booking(db, charger, alice, slot(0, 60))
    for status in path:
        db.execute("UPDATE bookings SET status = %s WHERE booking_id = %s", (status, first))
    make_booking(db, charger, bob, slot(0, 60))  # same slot is free again


def test_expired_hold_frees_the_slot(db):
    charger, alice, bob = make_charger(db), make_user(db, "a@t.dev"), make_user(db, "b@t.dev")
    held = make_booking(db, charger, alice, slot(0, 60), status="HELD", source="APP")
    db.execute("UPDATE bookings SET status = 'EXPIRED' WHERE booking_id = %s", (held,))
    make_booking(db, charger, bob, slot(0, 60))


def test_a_user_can_hold_only_one_slot_at_a_time(db):
    alice = make_user(db)
    make_booking(db, make_charger(db), alice, slot(0, 30), status="HELD", source="APP")
    with pytest.raises(errors.UniqueViolation):
        make_booking(db, make_charger(db), alice, slot(120, 30), status="HELD", source="APP")


def test_app_booking_requires_a_user(db):
    with pytest.raises(errors.CheckViolation, match="bookings_user_required"):
        make_booking(db, make_charger(db), None, slot(0, 30), status="HELD", source="APP")


def test_walk_in_booking_needs_no_user(db):
    make_booking(db, make_charger(db), None, slot(0, 30), status="HELD", source="WALK_IN")


def test_walk_in_cannot_overlap_an_app_booking(db):
    charger = make_charger(db)
    make_booking(db, charger, make_user(db), slot(0, 60))
    with pytest.raises(errors.ExclusionViolation):
        make_booking(db, charger, None, slot(45, 30), status="HELD", source="WALK_IN")


@pytest.mark.parametrize("bad_range", [
    "(2026-10-12 04:30+00, 2026-10-12 05:00+00]",   # wrong bounds: must be [start, end)
    "[2026-10-12 05:00+00, 2026-10-12 05:00+00)",   # empty: zero length
    "[2026-10-12 04:30+00,)",                        # open-ended
])
def test_time_range_must_be_a_finite_start_inclusive_span(db, bad_range):
    with pytest.raises(errors.CheckViolation):
        make_booking(db, make_charger(db), make_user(db), bad_range)


# ---------- status rules (the transition trigger) ----------

def test_illegal_status_change_is_rejected(db):
    booking = make_booking(db, make_charger(db), make_user(db), slot(0, 30))
    db.execute("UPDATE bookings SET status = 'ACTIVE' WHERE booking_id = %s", (booking,))
    db.execute("UPDATE bookings SET status = 'COMPLETED' WHERE booking_id = %s", (booking,))
    with pytest.raises(errors.CheckViolation, match="Illegal booking status change: COMPLETED -> HELD"):
        db.execute("UPDATE bookings SET status = 'HELD' WHERE booking_id = %s", (booking,))


@pytest.mark.parametrize("source, start_status", [
    ("APP", "CONFIRMED"),       # an app booking must be paid for first (start as HELD)
    ("APP", "ACTIVE"),
    ("WALK_IN", "CONFIRMED"),
    ("INSTANT", "HELD"),
])
def test_new_bookings_must_start_in_the_right_status(db, source, start_status):
    user = None if source == "WALK_IN" else make_user(db)
    with pytest.raises(errors.CheckViolation, match="Illegal booking status change"):
        make_booking(db, make_charger(db), user, slot(0, 30), status=start_status, source=source)


def test_only_walk_ins_go_straight_from_held_to_active(db):
    app_booking = make_booking(db, make_charger(db), make_user(db), slot(0, 30), status="HELD", source="APP")
    with pytest.raises(errors.CheckViolation):
        db.execute("UPDATE bookings SET status = 'ACTIVE' WHERE booking_id = %s", (app_booking,))


def test_every_status_change_is_recorded_with_actor_and_reason(db):
    booking = make_booking(db, make_charger(db), make_user(db), slot(0, 30), status="HELD", source="APP")
    db.execute("SELECT set_config('chargespot.actor', 'USER', true), set_config('chargespot.reason', 'Paid', true)")
    db.execute("UPDATE bookings SET status = 'CONFIRMED' WHERE booking_id = %s", (booking,))
    events = db.execute(
        "SELECT from_status, to_status, actor, reason FROM booking_events WHERE booking_id = %s ORDER BY event_id",
        (booking,),
    ).fetchall()
    assert events == [(None, "HELD", "SYSTEM", None), ("HELD", "CONFIRMED", "USER", "Paid")]


def test_non_status_updates_do_not_create_events(db):
    booking = make_booking(db, make_charger(db), make_user(db), slot(0, 30))
    db.execute("UPDATE bookings SET cancel_reason = 'note' WHERE booking_id = %s", (booking,))
    count = db.execute("SELECT count(*) FROM booking_events WHERE booking_id = %s", (booking,)).fetchone()[0]
    assert count == 1  # only the creation event


def test_concurrent_bookings_for_the_same_slot_only_one_wins(migrated_db):
    """Two separate connections book the same slot at the same moment.

    When both inserts land at exactly the same instant, each waits for the other to
    finish, and PostgreSQL may break the tie with a deadlock error (40P01) instead of
    the exclusion error (23P01). Either way no double booking happens. The rule for the
    API (Phase 4): on 40P01, retry the booking once; the retry then gets a clean 23P01.
    """
    import threading

    from database import common

    with common.connect("TEST_DATABASE_URL") as setup:
        charger = make_charger(setup)
        users = [make_user(setup, f"race{i}@t.dev") for i in range(2)]
        setup.commit()

    barrier = threading.Barrier(2)
    results = []

    def attempt(user_id):
        with common.connect("TEST_DATABASE_URL") as conn:
            barrier.wait()
            for _ in range(2):  # first try + one retry after a deadlock
                try:
                    make_booking(conn, charger, user_id, slot(0, 60))
                    conn.commit()
                    results.append("booked")
                    return
                except psycopg.errors.ExclusionViolation:
                    conn.rollback()
                    results.append("slot taken")
                    return
                except psycopg.errors.DeadlockDetected:
                    conn.rollback()
            results.append("gave up")

    threads = [threading.Thread(target=attempt, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    try:
        assert sorted(results) == ["booked", "slot taken"]
    finally:
        with common.connect("TEST_DATABASE_URL") as cleanup:
            cleanup.execute("DELETE FROM booking_events WHERE booking_id IN (SELECT booking_id FROM bookings WHERE charger_id = %s)", (charger,))
            cleanup.execute("DELETE FROM bookings WHERE charger_id = %s", (charger,))
            cleanup.execute("DELETE FROM stations WHERE station_id = (SELECT station_id FROM chargers WHERE charger_id = %s)", (charger,))
            cleanup.execute("DELETE FROM users WHERE user_id = ANY(%s)", (users,))
            cleanup.commit()
