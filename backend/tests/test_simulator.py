"""The charger simulator, outside sessions, and the lazy checks (needs the test database)."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.errors import AppError
from app.core.slots import ist_date
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.availability import service as availability
from app.features.bookings import service as bookings
from app.features.chargers import service as simulator
from app.features.jobs import lazy
from app.main import app
from tests import factories
from tests.conftest import needs_db

pytestmark = needs_db

START = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
M = timedelta(minutes=1)


def _committed(make):
    def wrapper(db, *args, **kwargs):
        result = make(db, *args, **kwargs)
        db.commit()
        return result

    return wrapper


make_station = _committed(factories.make_station)
make_charger = _committed(factories.make_charger)
make_user = _committed(factories.make_user)
make_booking = _committed(factories.make_booking)


@pytest.fixture
def world(db):
    station = make_station(db, "Sim hub", 23.03, 72.55)
    return {
        "station": station,
        "a": make_charger(db, station, "CCS2", 60, 20, label="CCS2-1"),
        "b": make_charger(db, station, "CCS2", 60, 20, label="CCS2-2"),
        "user": make_user(db),
        "other": make_user(db),
    }


def simulate(db, charger, event, now):
    return simulator.simulate(db, charger, event, now)


def paid(db, booking_id, amount=199):
    db.execute(
        text("INSERT INTO payments (booking_id, purpose, provider_order_id, provider_payment_id, amount, status) VALUES (:b, 'BOOKING_FEE', :o, :p, :a, 'CAPTURED')"),
        {"b": booking_id, "o": f"order_{booking_id}", "p": f"pay_{booking_id}", "a": amount},
    )
    db.commit()


def block_states(db, world, now, charger="a"):
    grid = availability.station_availability(db, world["station"], ist_date(now), now)
    [row] = [c for c in grid.chargers if c.charger_id == world[charger]]
    return {block.start: block.state for block in row.blocks}


# ---------------------------------------------------------------- the events

def test_an_outside_start_is_accepted_when_nothing_is_booked_and_it_makes_a_session(db, world):
    result = simulate(db, world["a"], "EXTERNAL_START", START)
    assert result["accepted"] is True and result["status"] == "CHARGING" and result["session_id"]
    row = db.execute(text("SELECT source, booking_id, ended_at FROM charging_sessions WHERE session_id = :s"), {"s": result["session_id"]}).one()
    assert tuple(row) == ("EXTERNAL", None, None)


def test_a_reserved_charger_refuses_an_outside_start(db, world):
    make_booking(db, world["a"], START + 10 * M, START + 70 * M, user_id=world["user"])  # starts in 10 minutes: inside the 15-minute lock
    result = simulate(db, world["a"], "EXTERNAL_START", START)
    assert result["accepted"] is False and "reserved" in result["reason"] and result["status"] == "AVAILABLE"
    assert db.execute(text("SELECT count(*) FROM charging_sessions WHERE charger_id = :c"), {"c": world["a"]}).scalar_one() == 0
    assert db.execute(text("SELECT event FROM charger_events WHERE charger_id = :c ORDER BY event_id DESC LIMIT 1"), {"c": world["a"]}).scalar_one() == "REJECTED_EXTERNAL_START"
    assert simulate(db, world["b"], "EXTERNAL_START", START)["accepted"] is True  # the other charger is not booked


def test_the_other_events(db, world):
    assert simulate(db, world["a"], "FAULT", START)["status"] == "FAULTED"
    assert simulate(db, world["a"], "EXTERNAL_START", START + M)["accepted"] is False
    assert simulate(db, world["a"], "RECOVER", START + 2 * M)["status"] == "AVAILABLE"
    simulate(db, world["a"], "EXTERNAL_START", START + 3 * M)
    assert simulate(db, world["a"], "UNPLUG", START + 10 * M)["status"] == "AVAILABLE"
    assert simulate(db, world["a"], "EXTERNAL_STOP", START + 11 * M)["accepted"] is False  # nothing left to stop


def test_unknown_events_and_chargers_are_clear_errors(db, world):
    with pytest.raises(AppError) as error:
        simulate(db, world["a"], "EXPLODE", START)
    assert error.value.status_code == 422 and error.value.code == "UNKNOWN_EVENT"
    with pytest.raises(AppError) as error:
        simulate(db, "00000000-0000-0000-0000-000000000000", "FAULT", START)
    assert error.value.status_code == 404 and error.value.code == "CHARGER_NOT_FOUND"


# ---------------------------------------------------------------- what the grid shows

def test_an_outside_session_makes_only_the_current_block_busy_external(db, world):
    simulate(db, world["a"], "EXTERNAL_START", START + 5 * M)
    states = block_states(db, world, START + 10 * M)
    current = START  # the 10:00-10:30 block contains 10:10
    assert states[current] == "BUSY_EXTERNAL"
    assert states[current + 30 * M] == "FREE" and states[current - 30 * M] == "PAST"
    assert block_states(db, world, START + 10 * M, "b")[current] == "FREE"  # the other charger is unaffected
    simulate(db, world["a"], "EXTERNAL_STOP", START + 12 * M)
    assert block_states(db, world, START + 13 * M)[current] == "FREE"


def test_a_broken_charger_shows_out_of_service(db, world):
    simulate(db, world["a"], "FAULT", START)
    assert set(v for k, v in block_states(db, world, START).items() if k >= START) == {"OUT_OF_SERVICE"}


# ---------------------------------------------------------------- the driver's side

def test_a_booking_is_moved_to_a_free_charger_and_the_driver_sees_why(db, world):
    booking = make_booking(db, world["a"], START, START + 60 * M, user_id=world["user"])
    simulate(db, world["a"], "EXTERNAL_START", START - 30 * M)  # someone else is still charging at the start time
    seen = bookings.get_booking(db, world["user"], booking, START)  # the lazy check does the move
    assert seen.status == "CONFIRMED" and seen.charger.label == "CCS2-2" and (seen.start, seen.end) == (START, START + 60 * M)
    assert (seen.notice_kind, seen.notice_text) == ("MOVED", "Moved from CCS2-1 to CCS2-2, same time.")
    assert bookings.my_bookings(db, world["user"], "upcoming", START)[0].notice_kind == "MOVED"


def test_when_no_charger_is_free_the_booking_is_cancelled_with_a_full_refund(db, world):
    booking = make_booking(db, world["a"], START, START + 60 * M, user_id=world["user"])
    paid(db, booking)
    make_booking(db, world["b"], START + 10 * M, START + 40 * M, user_id=world["other"])
    simulate(db, world["a"], "EXTERNAL_START", START - 30 * M)
    seen = bookings.get_booking(db, world["user"], booking, START + M)
    assert seen.status == "CANCELLED" and seen.refund_amount == 199.0 and seen.notice_kind == "CANCELLED_NO_CHARGER"
    assert "refunded in full" in seen.notice_text
    payment = db.execute(text("SELECT status, refunded_amount FROM payments WHERE booking_id = :b"), {"b": booking}).one()
    assert (payment.status, float(payment.refunded_amount)) == ("REFUNDED", 199.0)


def test_the_driver_is_warned_while_an_outside_session_is_still_running_before_their_start(db, world):
    booking = make_booking(db, world["a"], START + 10 * M, START + 70 * M, user_id=world["user"])
    simulate(db, world["a"], "EXTERNAL_START", START - 20 * M)
    seen = bookings.get_booking(db, world["user"], booking, START)  # 10 minutes before the start: the lock time has passed
    assert seen.notice_kind == "WARNING" and "still charging" in seen.notice_text
    simulate(db, world["a"], "EXTERNAL_STOP", START + 2 * M)
    assert bookings.get_booking(db, world["user"], booking, START + 3 * M).notice_kind is None


# ---------------------------------------------------------------- lazy checks

def test_reading_availability_makes_an_overdue_no_show_happen(db, world):
    booking = make_booking(db, world["a"], START, START + 60 * M, user_id=world["user"])
    availability.station_availability(db, world["station"], ist_date(START), START + 11 * M)
    assert db.execute(text("SELECT status FROM bookings WHERE booking_id = :b"), {"b": booking}).scalar_one() == "NO_SHOW"
    assert set(block_states(db, world, START + 11 * M)[START + 30 * M:START + 30 * M + M] if False else [block_states(db, world, START + 11 * M)[START + 30 * M]]) == {"FREE"}


def test_reading_availability_expires_a_hold_that_ran_out(db, world):
    hold = bookings.create_hold(db, world["user"], world["a"], START + 2 * 60 * M, 1, None, START)
    states = block_states(db, world, START + 6 * M)
    assert states[START + 2 * 60 * M] == "FREE"
    assert db.execute(text("SELECT status FROM bookings WHERE booking_id = :b"), {"b": hold.booking_id}).scalar_one() == "EXPIRED"


def test_the_lazy_check_never_breaks_a_read(db, caplog):
    class Broken:
        rolled_back = False

        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT", {}, Exception("deadlock detected"))

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            raise AssertionError("must not commit after a failure")

    broken = Broken()
    assert lazy.run_due_jobs(broken, START) is None and broken.rolled_back


def test_the_lazy_check_returns_what_the_jobs_did(db, world):
    make_booking(db, world["a"], START - 60 * M, START, user_id=world["user"])
    result = lazy.run_due_jobs(db, START + 15 * M, world["station"])
    assert result["mark_no_shows"] == 1 and set(result) == {
        "expire_holds", "resolve_occupied_starts", "mark_no_shows", "auto_stop_sessions", "apply_reservation_locks"}


# ---------------------------------------------------------------- over HTTP

def as_user(user_id, role="USER"):
    app.dependency_overrides[get_current_user] = lambda: User(user_id=user_id, email="x@test.dev", role=role)


def test_simulator_endpoints_are_for_admins_only(db_client, world):
    as_user(world["user"])
    assert db_client.post(f"/api/admin/chargers/{world['a']}/simulate", json={"event": "FAULT"}).status_code == 403
    assert db_client.post(f"/api/admin/bookings/{'0' * 8}-0000-0000-0000-{'0' * 12}/start").status_code == 403


def test_http_simulate_as_admin(db_client, db, world):
    as_user(world["user"], role="ADMIN")
    ok = db_client.post(f"/api/admin/chargers/{world['a']}/simulate", json={"event": "EXTERNAL_START"})
    assert ok.status_code == 200 and ok.json()["accepted"] is True and ok.json()["status"] == "CHARGING"
    again = db_client.post(f"/api/admin/chargers/{world['a']}/simulate", json={"event": "EXTERNAL_START"})
    assert again.status_code == 200 and again.json()["accepted"] is False and again.json()["reason"]  # a refusal is an answer, not an error
    assert db_client.post(f"/api/admin/chargers/{world['a']}/simulate", json={"event": "EXPLODE"}).status_code == 422
    missing = db_client.post("/api/admin/chargers/00000000-0000-0000-0000-000000000000/simulate", json={"event": "FAULT"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "CHARGER_NOT_FOUND"


def test_http_admin_can_start_a_booking_like_the_kiosk_will(db_client, db, world):
    now = datetime.now(timezone.utc)
    booking = make_booking(db, world["b"], now + 5 * M, now + 65 * M, user_id=world["user"])
    as_user(world["user"], role="ADMIN")
    started = db_client.post(f"/api/admin/bookings/{booking}/start")
    assert started.status_code == 200 and started.json()["booking_id"] == str(booking)
    again = db_client.post(f"/api/admin/bookings/{booking}/start")
    assert again.status_code == 409 and again.json()["error"]["code"] == "BOOKING_NOT_STARTABLE"
    as_user(world["user"])
    live = db_client.get(f"/api/me/sessions/{started.json()['session_id']}").json()
    assert live["status"] == "RUNNING" and live["charger"]["label"] == "CCS2-2"
