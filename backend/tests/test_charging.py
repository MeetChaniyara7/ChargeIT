"""Charging sessions: starting, the live numbers, stopping, and the lazy auto-stop (needs the test database).

Service functions take `now`, so these tests pretend to be at chosen moments of Monday 2026-10-12.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.bookings import service as bookings
from app.features.charging import service
from app.main import app
from tests import factories
from tests.conftest import needs_db

pytestmark = needs_db

START = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)  # a booking starting 15:30 IST
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


def add_vehicle(db, user_id, battery=100, connector="CCS2"):
    vehicle_id = db.execute(
        text("INSERT INTO vehicles (user_id, nickname, connector_type, battery_kwh) VALUES (:u, 'Car', :c, :b) RETURNING vehicle_id"),
        {"u": user_id, "c": connector, "b": battery},
    ).scalar_one()
    db.commit()
    return vehicle_id


@pytest.fixture
def world(db):
    station = make_station(db, "Charge hub", 23.03, 72.55)
    user, other = make_user(db), make_user(db)
    return {
        "station": station,
        "charger": make_charger(db, station, "CCS2", 60, 20, label="CCS2-1"),
        "second": make_charger(db, station, "CCS2", 60, 20, label="CCS2-2"),
        "user": user,
        "other": other,
        "vehicle": add_vehicle(db, user, 100),
    }


def confirmed(db, world, start=START, minutes=60, vehicle=True, user="user", charger="charger"):
    booking_id = make_booking(db, world[charger], start, start + minutes * M, user_id=world[user])
    if vehicle:
        db.execute(text("UPDATE bookings SET vehicle_id = :v WHERE booking_id = :b"), {"v": world["vehicle"], "b": booking_id})
        db.commit()
    return booking_id


def start(db, booking_id, at=START):
    return service.start_session(db, booking_id, at, actor="ADMIN")


def status_of(db, booking_id):
    return db.execute(text("SELECT status FROM bookings WHERE booking_id = :b"), {"b": booking_id}).scalar_one()


def charger_status(db, charger_id):
    return db.execute(text("SELECT status FROM chargers WHERE charger_id = :c"), {"c": charger_id}).scalar_one()


# ---------------------------------------------------------------- starting

def test_starting_activates_the_booking_uses_the_code_and_puts_the_charger_to_charging(db, world):
    booking_id = confirmed(db, world)
    session = start(db, booking_id)
    assert (status_of(db, booking_id), charger_status(db, world["charger"])) == ("ACTIVE", "CHARGING")
    assert db.execute(text("SELECT otp_used_at FROM bookings WHERE booking_id = :b"), {"b": booking_id}).scalar_one() == START
    assert (session.source, session.started_at, float(session.start_soc_percent)) == ("BOOKING", START, 20.0)
    event = db.execute(text("SELECT from_status, to_status, actor FROM booking_events WHERE booking_id = :b ORDER BY event_id DESC LIMIT 1"), {"b": booking_id}).one()
    assert tuple(event) == ("CONFIRMED", "ACTIVE", "ADMIN")
    assert db.execute(text("SELECT event FROM charger_events WHERE charger_id = :c ORDER BY event_id DESC LIMIT 1"), {"c": world["charger"]}).scalar_one() == "SESSION_START"


def test_starting_a_reserved_charger_works(db, world):
    booking_id = confirmed(db, world)
    db.execute(text("SELECT apply_reservation_locks(:now)"), {"now": START - 10 * M})
    db.commit()
    assert charger_status(db, world["charger"]) == "RESERVED"
    start(db, booking_id)
    assert charger_status(db, world["charger"]) == "CHARGING"


def test_starting_is_refused_when_it_cannot_work(db, world):
    held = bookings.create_hold(db, world["other"], world["charger"], START + 3 * 60 * M, 1, None, START)
    with pytest.raises(AppError) as error:
        service.start_session(db, held.booking_id, START)
    assert error.value.code == "BOOKING_NOT_STARTABLE"

    booking_id = confirmed(db, world, charger="second")
    db.execute(text("SELECT simulate_charger_event(:c, 'FAULT', :now)"), {"c": world["second"], "now": START - M})
    db.commit()
    with pytest.raises(AppError) as error:
        start(db, booking_id)
    assert error.value.code == "CHARGER_UNAVAILABLE"
    assert status_of(db, booking_id) == "CONFIRMED"

    with pytest.raises(AppError) as error:
        service.start_session(db, "00000000-0000-0000-0000-000000000000", START)
    assert error.value.status_code == 404


def test_a_charger_in_use_by_an_outside_driver_cannot_start_a_booking(db, world):
    booking_id = confirmed(db, world, start=START + 60 * M)
    db.execute(text("SELECT simulate_charger_event(:c, 'EXTERNAL_START', :now)"), {"c": world["charger"], "now": START})
    db.commit()
    with pytest.raises(AppError) as error:
        start(db, booking_id)
    assert error.value.code == "CHARGER_UNAVAILABLE"


# ---------------------------------------------------------------- live numbers

def test_the_live_numbers_come_from_the_energy_formula(db, world):
    booking_id = confirmed(db, world)
    session = start(db, booking_id)
    live = service.get_session(db, world["user"], session.session_id, START + 30 * M)
    # 60 kW for 30 minutes at 90% = 27 kWh into a 100 kWh battery that started at 20%
    assert live.status == "RUNNING" and live.source == "BOOKING"
    assert live.energy_kwh == 27.0 and live.battery_percent == 47.0 and live.cost_so_far == 540.0
    assert live.seconds_left == 30 * 60 and live.duration_minutes == 30.0
    assert live.planned_stop_at == START + 60 * M and live.server_time == START + 30 * M
    assert (live.station.name, live.charger.label, live.charger.power_kw, live.charger.price_per_kwh) == ("Charge hub", "CCS2-1", 60.0, 20.0)
    assert live.can_stop and not live.stop_warning and live.ended_at is None and live.bill_amount is None


def test_the_battery_stops_filling_at_100_percent(db, world):
    small = add_vehicle(db, world["user"], 30)
    booking_id = make_booking(db, world["charger"], START, START + 120 * M, user_id=world["user"])
    db.execute(text("UPDATE bookings SET vehicle_id = :v WHERE booking_id = :b"), {"v": small, "b": booking_id})
    db.commit()
    session = start(db, booking_id)
    live = service.get_session(db, world["user"], session.session_id, START + 119 * M)
    assert (live.energy_kwh, live.battery_percent, live.cost_so_far) == (24.0, 100.0, 480.0)  # 30 kWh x 80% of room


def test_a_session_without_a_vehicle_uses_the_default_battery(db, world):
    booking_id = confirmed(db, world, vehicle=False)
    session = start(db, booking_id)
    live = service.get_session(db, world["user"], session.session_id, START + 30 * M)
    # 27 kWh fits in the default 40 kWh battery that started at 20% (room for 32), so nothing is cut off
    assert live.energy_kwh == 27.0 and live.battery_percent == 87.5
    later = service.get_session(db, world["user"], session.session_id, START + 50 * M)
    assert later.energy_kwh == 32.0 and later.battery_percent == 100.0  # now it is full


def test_the_warning_comes_five_minutes_before_the_automatic_stop(db, world):
    booking_id = confirmed(db, world)
    session = start(db, booking_id)
    assert not service.get_session(db, world["user"], session.session_id, START + 54 * M).stop_warning  # 6 minutes left
    at_five = service.get_session(db, world["user"], session.session_id, START + 55 * M)
    assert at_five.stop_warning and at_five.seconds_left == 300
    assert not at_five.next_booking_waiting


def test_next_booking_waiting_when_another_driver_starts_soon_after(db, world):
    booking_id = confirmed(db, world)
    confirmed(db, world, start=START + 60 * M, user="other")
    session = start(db, booking_id)
    assert service.get_session(db, world["user"], session.session_id, START + 56 * M).next_booking_waiting
    far = confirmed(db, world, start=START + 5 * 60 * M, user="other", charger="second")
    assert far  # on another charger entirely: not relevant


def test_next_booking_not_waiting_when_it_is_far_off(db, world):
    booking_id = confirmed(db, world)
    confirmed(db, world, start=START + 120 * M, user="other")
    session = start(db, booking_id)
    assert not service.get_session(db, world["user"], session.session_id, START + 56 * M).next_booking_waiting


# ---------------------------------------------------------------- stopping

def test_stopping_bills_up_to_now_and_completes_the_booking(db, world):
    booking_id = confirmed(db, world)
    session = start(db, booking_id)
    result = service.stop_session(db, world["user"], session.session_id, START + 30 * M)
    assert result.status == "ENDED" and result.end_reason == "USER_STOP" and result.can_stop is False
    assert (result.energy_kwh, result.bill_amount, result.cost_so_far, result.bill_status) == (27.0, 540.0, 540.0, "DUE")
    assert result.ended_at == START + 30 * M and result.duration_minutes == 30.0 and result.seconds_left is None
    assert status_of(db, booking_id) == "COMPLETED" and charger_status(db, world["charger"]) == "AVAILABLE"
    event = db.execute(text("SELECT actor FROM booking_events WHERE booking_id = :b AND to_status = 'COMPLETED'"), {"b": booking_id}).scalar_one()
    assert event == "USER"


def test_stopping_twice_changes_nothing(db, world):
    session = start(db, confirmed(db, world))
    first = service.stop_session(db, world["user"], session.session_id, START + 30 * M)
    again = service.stop_session(db, world["user"], session.session_id, START + 45 * M)
    assert (again.ended_at, again.energy_kwh, again.bill_amount) == (first.ended_at, first.energy_kwh, first.bill_amount)


def test_a_session_past_its_slot_end_is_stopped_the_moment_it_is_read(db, world):
    """No job has run: reading the session does the automatic stop, and bills exactly the booked time."""
    booking_id = confirmed(db, world)
    session = start(db, booking_id)
    live = service.get_session(db, world["user"], session.session_id, START + 75 * M)
    assert live.status == "ENDED" and live.end_reason == "SLOT_END_AUTO_STOP"
    assert live.ended_at == START + 60 * M and (live.energy_kwh, live.bill_amount) == (54.0, 1080.0)
    assert status_of(db, booking_id) == "COMPLETED"


def test_the_unpaid_bill_after_a_session_blocks_new_bookings(db, world):
    session = start(db, confirmed(db, world))
    service.stop_session(db, world["user"], session.session_id, START + 30 * M)
    dues = bookings.unpaid_bills(db, world["user"])
    assert (dues.count, dues.total) == (1, 540.0)
    with pytest.raises(AppError) as error:
        bookings.create_hold(db, world["user"], world["charger"], START + 3 * 60 * M, 1, None, START + 40 * M)
    assert error.value.code == "UNPAID_BILL"


def test_only_the_owner_can_see_or_stop_a_session(db, world):
    session = start(db, confirmed(db, world))
    for call in (service.get_session, service.stop_session):
        with pytest.raises(AppError) as error:
            call(db, world["other"], session.session_id, START + M)
        assert error.value.status_code == 404 and error.value.code == "SESSION_NOT_FOUND"
    assert service.get_session(db, world["user"], session.session_id, START + M).status == "RUNNING"


def test_the_active_session(db, world):
    assert service.active_session(db, world["user"], START) is None
    session = start(db, confirmed(db, world))
    active = service.active_session(db, world["user"], START + 10 * M)
    assert active.session_id == session.session_id and active.battery_percent > 20
    assert service.active_session(db, world["other"], START + 10 * M) is None
    service.stop_session(db, world["user"], session.session_id, START + 20 * M)
    assert service.active_session(db, world["user"], START + 21 * M) is None


def test_the_booking_links_to_its_live_page(db, world):
    booking_id = confirmed(db, world)
    assert bookings.get_booking(db, world["user"], booking_id, START).session_id is None
    session = start(db, booking_id)
    assert bookings.get_booking(db, world["user"], booking_id, START + M).session_id == session.session_id
    [listed] = bookings.my_bookings(db, world["user"], "upcoming", START + M)
    assert listed.session_id == session.session_id and listed.status == "ACTIVE"


# ---------------------------------------------------------------- over HTTP (real clock)

def sign_in(user_id):
    app.dependency_overrides[get_current_user] = lambda: User(user_id=user_id, email="driver@test.dev", role="USER")


def test_session_endpoints_need_a_login(client):
    for method, path in [("get", "/api/me/sessions/active"), ("get", f"/api/me/sessions/{'0' * 8}-0000-0000-0000-{'0' * 12}"), ("post", f"/api/me/sessions/{'0' * 8}-0000-0000-0000-{'0' * 12}/stop")]:
        assert getattr(client, method)(path).status_code == 401


def test_http_no_active_session_is_null_and_an_unknown_session_is_404(db_client, world):
    sign_in(world["user"])
    response = db_client.get("/api/me/sessions/active")
    assert response.status_code == 200 and response.json() is None
    missing = db_client.get("/api/me/sessions/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert db_client.get("/api/me/sessions/not-a-uuid").status_code == 422


def test_http_live_session_and_stop(db_client, db, world):
    now = datetime.now(timezone.utc)
    booking_id = make_booking(db, world["charger"], now - 5 * M, now + 55 * M, user_id=world["user"])
    session = service.start_session(db, booking_id, now - 5 * M, actor="ADMIN")
    sign_in(world["user"])
    body = db_client.get(f"/api/me/sessions/{session.session_id}").json()
    assert body["status"] == "RUNNING" and body["energy_kwh"] > 0 and 0 < body["seconds_left"] <= 55 * 60
    assert db_client.get("/api/me/sessions/active").json()["session_id"] == str(session.session_id)
    stopped = db_client.post(f"/api/me/sessions/{session.session_id}/stop").json()
    assert stopped["status"] == "ENDED" and stopped["end_reason"] == "USER_STOP" and stopped["bill_status"] in ("DUE", "PAID")
    assert db_client.get("/api/me/sessions/active").json() is None
