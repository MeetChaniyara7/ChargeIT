"""Holding a slot, "Charge now", codes and cancelling (needs the test database).

Service functions take `now` as an argument, so these tests run at a fixed moment: Monday
2026-10-12 10:00 UTC. The HTTP tests at the bottom use the real clock.
"""

import itertools
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.core.slots import ceil_to_slot
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.bookings import otp, service
from app.features.bookings.models import Booking
from app.features.recommendations import service as recommendations
from app.features.recommendations.osrm import Travel
from app.main import app
from tests import factories
from tests.conftest import needs_db
from tests.factories import HOUR

pytestmark = needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
_payment_numbers = itertools.count(1)


def _committed(make):
    """Test data is committed straight away, as it would be in the real database.

    The service rolls back when a booking is refused; without this, that rollback would
    also undo the rows the test had just created.
    """

    def wrapper(db, *args, **kwargs):
        result = make(db, *args, **kwargs)
        db.commit()
        return result

    return wrapper


make_booking = _committed(factories.make_booking)
make_charger = _committed(factories.make_charger)
make_due_bill = _committed(factories.make_due_bill)
make_station = _committed(factories.make_station)
make_user = _committed(factories.make_user)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 12, hour, minute, tzinfo=timezone.utc)


class FakeRoutes:
    """No network in tests: every station is 5 minutes away."""

    def estimate(self, origin, destinations):
        return [Travel(5.0 + i, 2.0 + i, True) for i, _ in enumerate(destinations)]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(recommendations, "travel_times", FakeRoutes())


@pytest.fixture
def world(db):
    """A station with two CCS2 chargers, and two drivers."""
    station = make_station(db, "Test hub", 23.03, 72.55)
    return {
        "station": station,
        "a": make_charger(db, station, "CCS2", 60, 20, label="A"),
        "b": make_charger(db, station, "CCS2", 60, 20, label="B"),
        "user": make_user(db),
        "other": make_user(db),
    }


def pay(db, booking_id, amount=199, status="CAPTURED"):
    n = next(_payment_numbers)
    db.execute(
        text(
            "INSERT INTO payments (booking_id, purpose, provider_order_id, provider_payment_id, amount, status) "
            "VALUES (:b, 'BOOKING_FEE', :o, :p, :a, :s)"
        ),
        {"b": booking_id, "o": f"order_test_{n}", "p": f"pay_test_{n}" if status != "CREATED" else None, "a": amount, "s": status},
    )
    db.commit()


def hold(db, world, charger="a", start=None, blocks=2, user="user", now=NOW):
    return service.create_hold(db, world[user], world[charger], start or at(12), blocks, None, now)


def booking_status(db, booking_id):
    return db.execute(text("SELECT status FROM bookings WHERE booking_id = :b"), {"b": booking_id}).scalar_one()


# ---------------------------------------------------------------- holding a slot

def test_a_hold_lasts_five_minutes_and_costs_199(db, world):
    booking = hold(db, world)
    assert booking.status == "HELD" and booking.source == "APP"
    assert booking.start == at(12) and booking.end == at(13) and booking.blocks == 2
    assert booking.hold_expires_at == NOW + timedelta(minutes=5)
    assert booking.booking_fee == 199 and booking.fee_paid is False and booking.can_cancel
    event = db.execute(text("SELECT actor, to_status FROM booking_events WHERE booking_id = :b"), {"b": booking.booking_id}).one()
    assert tuple(event) == ("USER", "HELD")


@pytest.mark.parametrize(
    "start, blocks, code",
    [
        (at(12, 10), 1, "SLOT_NOT_ALIGNED"),
        (at(9, 30), 1, "START_IN_PAST"),
        (NOW, 1, "START_IN_PAST"),
        (NOW + timedelta(days=7), 1, "START_TOO_FAR"),
        (at(12), 0, "INVALID_BLOCKS"),
        (at(12), 5, "INVALID_BLOCKS"),
    ],
)
def test_invalid_requests_are_refused(db, world, start, blocks, code):
    with pytest.raises(AppError) as error:
        service.create_hold(db, world["user"], world["a"], start, blocks, None, NOW)
    assert error.value.code == code and error.value.status_code == 422


def test_the_last_slot_within_seven_days_is_allowed(db, world):
    booking = service.create_hold(db, world["user"], world["a"], NOW + timedelta(days=6, hours=23, minutes=30), 1, None, NOW)
    assert booking.status == "HELD"


def test_a_taken_slot_is_refused_with_alternatives_and_leaves_nothing_behind(db, world):
    make_booking(db, world["a"], at(12), at(13), user_id=world["other"])  # confirmed
    with pytest.raises(AppError) as error:
        hold(db, world, "a", at(12, 30), blocks=1)
    assert error.value.status_code == 409 and error.value.code == "SLOT_TAKEN"
    found = error.value.details["alternatives"]
    assert found["charger_id"] == str(world["a"]) and found["blocks"] == 1
    # Other times on the same charger: aligned, in the future and clear of the 12:00-13:00 booking.
    assert found["same_charger"]
    for alt in found["same_charger"]:
        start, end = datetime.fromisoformat(alt["start"]), datetime.fromisoformat(alt["end"])
        assert start > NOW and not (start < at(13) and end > at(12)) and start.minute in (0, 30)
    # The other charger here is free for exactly the requested time.
    [other] = found["other_chargers"]
    assert other["charger_id"] == str(world["b"]) and datetime.fromisoformat(other["start"]) == at(12, 30)
    assert db.scalar(text("SELECT count(*) FROM bookings WHERE user_id = :u"), {"u": world["user"]}) == 0


def test_alternatives_leave_out_chargers_that_are_busy_or_a_different_plug(db, world):
    make_charger(db, world["station"], "TYPE2", 22, 10, label="T2")  # another plug
    make_booking(db, world["a"], at(12), at(13), user_id=world["other"])
    make_booking(db, world["b"], at(12), at(13), user_id=make_user(db))
    with pytest.raises(AppError) as error:
        hold(db, world, "a", at(12), blocks=2)
    assert error.value.details["alternatives"]["other_chargers"] == []


def test_alternatives_include_a_nearby_station(db, world):
    make_booking(db, world["a"], at(12), at(13), user_id=world["other"])
    make_booking(db, world["b"], at(12), at(13), user_id=make_user(db))
    make_charger(db, make_station(db, "Next door", 23.031, 72.551), "CCS2", 50, 18)
    with pytest.raises(AppError) as error:
        hold(db, world, "a", at(12), blocks=2)
    [station] = error.value.details["alternatives"]["stations"]
    assert station["name"] == "Next door" and station["reason"] and datetime.fromisoformat(station["start"]) == at(12)


def test_somebody_elses_live_hold_blocks_the_slot(db, world):
    hold(db, world, "a", at(12), user="other")
    with pytest.raises(AppError) as error:
        hold(db, world, "a", at(12))
    assert error.value.code == "SLOT_TAKEN"


def test_an_expired_hold_frees_the_slot_straight_away_without_waiting_for_the_job(db, world):
    stale = make_booking(db, world["a"], at(12), at(13), status="HELD", hold_expires_at=NOW - timedelta(minutes=1), user_id=world["other"])
    assert booking_status(db, stale) == "HELD"  # the background job has not run
    booking = hold(db, world, "a", at(12))
    assert booking.status == "HELD" and booking.booking_id != stale
    assert booking_status(db, stale) == "EXPIRED"
    reason = db.execute(text("SELECT actor, reason FROM booking_events WHERE booking_id = :b AND to_status = 'EXPIRED'"), {"b": stale}).one()
    assert tuple(reason) == ("SYSTEM", "Hold ran out")


def test_a_hold_with_exactly_zero_seconds_left_counts_as_expired(db, world):
    make_booking(db, world["a"], at(12), at(13), status="HELD", hold_expires_at=NOW, user_id=world["other"])
    assert hold(db, world, "a", at(12)).status == "HELD"


def test_only_one_unpaid_hold_per_user(db, world):
    first = hold(db, world, "a", at(12))
    with pytest.raises(AppError) as error:
        hold(db, world, "b", at(14))
    assert error.value.status_code == 409 and error.value.code == "ACTIVE_HOLD_EXISTS"
    assert error.value.details == {"booking_id": str(first.booking_id)}


def test_ones_own_expired_hold_does_not_count_against_the_one_hold_rule(db, world):
    stale = make_booking(db, world["b"], at(14), at(15), status="HELD", hold_expires_at=NOW - HOUR, user_id=world["user"])
    assert hold(db, world, "a", at(12)).status == "HELD"
    assert booking_status(db, stale) == "EXPIRED"


def test_an_unpaid_bill_blocks_new_bookings(db, world):
    make_due_bill(db, world["user"], world["b"], 223.20)
    with pytest.raises(AppError) as error:
        hold(db, world)
    assert error.value.status_code == 409 and error.value.code == "UNPAID_BILL"
    assert error.value.details == {"count": 1, "total": 223.2}
    assert hold(db, world, user="other").status == "HELD"  # other people are not affected


def test_a_paid_bill_does_not_block(db, world):
    session = make_due_bill(db, world["user"], world["b"])
    db.execute(text("UPDATE charging_sessions SET bill_status = 'PAID' WHERE session_id = :s"), {"s": session})
    db.commit()
    assert hold(db, world).status == "HELD"


def test_chargers_that_cannot_be_booked(db, world):
    broken = make_charger(db, world["station"], "CCS2", 60, 20, status="OUT_OF_SERVICE")
    scooters = make_charger(db, make_station(db, "Scooters", category="TWO_WHEELER"), "TYPE2", 3, 5)
    closed = make_charger(db, make_station(db, "Closed", active=False), "CCS2", 60, 20)
    for charger_id, code in [(broken, "CHARGER_OUT_OF_SERVICE"), (scooters, "CHARGER_NOT_FOUND"), (closed, "CHARGER_NOT_FOUND"),
                             ("00000000-0000-0000-0000-000000000000", "CHARGER_NOT_FOUND")]:
        with pytest.raises(AppError) as error:
            service.create_hold(db, world["user"], charger_id, at(12), 1, None, NOW)
        assert error.value.code == code


def add_vehicle(db, user_id, connector="CCS2"):
    vehicle_id = db.execute(
        text("INSERT INTO vehicles (user_id, nickname, connector_type, battery_kwh) VALUES (:u, 'Car', :c, 40) RETURNING vehicle_id"),
        {"u": user_id, "c": connector},
    ).scalar_one()
    db.commit()
    return vehicle_id


def test_the_vehicle_must_be_yours_and_fit_the_charger(db, world):
    mine, wrong_plug, theirs = add_vehicle(db, world["user"]), add_vehicle(db, world["user"], "TYPE2"), add_vehicle(db, world["other"])
    assert service.create_hold(db, world["user"], world["a"], at(12), 1, mine, NOW).status == "HELD"
    service.cancel(db, world["user"], service.my_bookings(db, world["user"], "upcoming", NOW)[0].booking_id, NOW)
    with pytest.raises(AppError) as error:
        service.create_hold(db, world["user"], world["a"], at(14), 1, wrong_plug, NOW)
    assert error.value.code == "INCOMPATIBLE_VEHICLE"
    with pytest.raises(AppError) as error:
        service.create_hold(db, world["user"], world["a"], at(14), 1, theirs, NOW)
    assert error.value.code == "VEHICLE_NOT_FOUND"


def test_you_only_see_your_own_bookings(db, world):
    booking = hold(db, world)
    assert service.get_booking(db, world["user"], booking.booking_id, NOW).booking_id == booking.booking_id
    with pytest.raises(AppError) as error:
        service.get_booking(db, world["other"], booking.booking_id, NOW)
    assert error.value.status_code == 404
    assert service.my_bookings(db, world["other"], "upcoming", NOW) == []


def test_reading_an_expired_hold_marks_it_expired(db, world):
    booking = hold(db, world)
    later = NOW + timedelta(minutes=6)
    seen = service.get_booking(db, world["user"], booking.booking_id, later)
    assert seen.status == "EXPIRED" and seen.hold_expires_at is None and not seen.can_cancel
    assert booking_status(db, booking.booking_id) == "EXPIRED"


# ---------------------------------------------------------------- Charge now

def test_charge_now_is_free_confirmed_and_returns_a_code_once(db, world):
    booking = service.create_instant(db, world["user"], world["a"], None, NOW)
    assert booking.status == "CONFIRMED" and booking.source == "INSTANT" and booking.booking_fee == 0
    assert booking.start == NOW and booking.end == NOW + timedelta(hours=2)
    assert len(booking.otp) == 6 and booking.has_code
    stored = db.get(Booking, booking.booking_id).otp_hash
    assert booking.otp not in stored and otp.matches(booking.otp, stored)
    assert booking.otp not in service.get_booking(db, world["user"], booking.booking_id, NOW).model_dump_json()


def test_charge_now_stops_five_minutes_before_the_next_booking(db, world):
    make_booking(db, world["a"], NOW + timedelta(minutes=60), NOW + timedelta(minutes=120), user_id=world["other"])
    booking = service.create_instant(db, world["user"], world["a"], None, NOW)
    assert booking.end == NOW + timedelta(minutes=55)


def test_charge_now_takes_over_a_slot_whose_driver_never_showed_up(db, world):
    """Confirmed, started an hour ago, nobody entered the code: the lazy check makes it a no-show, freeing the charger."""
    unclaimed = make_booking(db, world["a"], NOW - HOUR, NOW + HOUR, user_id=world["other"])
    booking = service.create_instant(db, world["user"], world["a"], None, NOW)
    assert booking.status == "CONFIRMED"
    assert booking_status(db, unclaimed) == "NO_SHOW"


def test_charge_now_refuses_when_the_charger_is_busy_or_the_next_booking_is_too_close(db, world):
    busy = make_booking(db, world["a"], NOW - HOUR, NOW + HOUR, user_id=world["other"])
    db.execute(text("UPDATE bookings SET status = 'ACTIVE', otp_used_at = :t WHERE booking_id = :b"), {"t": NOW - HOUR, "b": busy})
    db.commit()  # someone is charging on it right now
    with pytest.raises(AppError) as error:
        service.create_instant(db, world["user"], world["a"], None, NOW)
    assert error.value.code == "CHARGER_BUSY"

    make_booking(db, world["b"], NOW + timedelta(minutes=12), NOW + HOUR, user_id=world["other"])
    with pytest.raises(AppError) as error:
        service.create_instant(db, world["user"], world["b"], None, NOW)
    assert error.value.code == "NO_ROOM_FOR_INSTANT"


def test_charge_now_needs_a_charger_that_is_available_and_no_unpaid_bill(db, world):
    in_use = make_charger(db, world["station"], "CCS2", 60, 20, status="CHARGING")
    with pytest.raises(AppError) as error:
        service.create_instant(db, world["user"], in_use, None, NOW)
    assert error.value.code == "CHARGER_BUSY"
    make_due_bill(db, world["user"], world["b"])
    with pytest.raises(AppError) as error:
        service.create_instant(db, world["user"], world["a"], None, NOW)
    assert error.value.code == "UNPAID_BILL"


def test_an_expired_hold_does_not_stop_charge_now(db, world):
    make_booking(db, world["a"], NOW - timedelta(minutes=10), NOW + HOUR, status="HELD", hold_expires_at=NOW - timedelta(minutes=5), user_id=world["other"])
    assert service.create_instant(db, world["user"], world["a"], None, NOW).status == "CONFIRMED"


# ---------------------------------------------------------------- codes

def confirmed(db, world, charger="a", start=None, user="user"):
    start = start or at(12)
    return make_booking(db, world[charger], start, start + HOUR, user_id=world[user])


def test_a_new_code_replaces_the_old_one(db, world):
    booking_id = confirmed(db, world)
    first = service.show_new_code(db, world["user"], booking_id, NOW)
    second = service.show_new_code(db, world["user"], booking_id, NOW)
    stored = db.get(Booking, booking_id).otp_hash
    assert first.valid_from == at(11, 45) and first.valid_until == at(12, 10)
    assert otp.matches(second.otp, stored)
    assert first.otp == second.otp or not otp.matches(first.otp, stored)  # the old code no longer works


def test_codes_at_one_station_are_unique_while_their_windows_overlap(db, world, monkeypatch):
    first_id, second_id = confirmed(db, world, "a"), confirmed(db, world, "b")
    draws = iter([123456, 123456, 654321])  # the second booking's first draw collides with the first booking's code
    monkeypatch.setattr(secrets, "randbelow", lambda n: next(draws))
    first = service.show_new_code(db, world["user"], first_id, NOW)
    second = service.show_new_code(db, world["user"], second_id, NOW)
    assert (first.otp, second.otp) == ("123456", "654321")


def test_codes_may_repeat_at_the_same_station_when_windows_do_not_overlap(db, world, monkeypatch):
    first_id, second_id = confirmed(db, world, "a", at(12)), confirmed(db, world, "a", at(15))
    monkeypatch.setattr(secrets, "randbelow", lambda n: 123456)
    assert service.show_new_code(db, world["user"], first_id, NOW).otp == service.show_new_code(db, world["user"], second_id, NOW).otp


def test_a_new_code_is_refused_when_there_is_nothing_to_show(db, world):
    too_late = service.show_new_code
    booking_id = confirmed(db, world)
    with pytest.raises(AppError) as error:
        too_late(db, world["user"], booking_id, at(12, 11))
    assert error.value.code == "CODE_WINDOW_ENDED"
    assert too_late(db, world["user"], booking_id, at(12, 10)).otp  # the last minute still works

    held = hold(db, world, "b", at(14))
    with pytest.raises(AppError) as error:
        too_late(db, world["user"], held.booking_id, NOW)
    assert error.value.code == "NO_CODE_FOR_STATUS"

    used = confirmed(db, world, "b", at(16))
    db.execute(text("UPDATE bookings SET otp_used_at = now() WHERE booking_id = :b"), {"b": used})
    db.commit()
    with pytest.raises(AppError) as error:
        too_late(db, world["user"], used, NOW)
    assert error.value.code == "CODE_ALREADY_USED"

    with pytest.raises(AppError) as error:
        too_late(db, world["other"], booking_id, NOW)
    assert error.value.status_code == 404


# ---------------------------------------------------------------- cancelling

@pytest.mark.parametrize(
    "cancel_at, percent, refund, payment_status",
    [
        (at(10), 100, "199.00", "REFUNDED"),          # exactly 2 hours before
        (at(10, 30), 75, "149.25", "PARTIALLY_REFUNDED"),
        (at(11, 30), 75, "149.25", "PARTIALLY_REFUNDED"),  # exactly 30 minutes
        (at(11, 31), 50, "99.50", "PARTIALLY_REFUNDED"),
        (at(11, 45), 50, "99.50", "PARTIALLY_REFUNDED"),   # exactly 15 minutes
        (at(11, 46), 0, "0.00", "CAPTURED"),
    ],
)
def test_cancelling_refunds_by_tier_and_records_it(db, world, cancel_at, percent, refund, payment_status):
    booking_id = confirmed(db, world)  # 12:00 start
    pay(db, booking_id)
    preview = service.cancel_preview(db, world["user"], booking_id, cancel_at)
    assert (preview.percent, preview.refund_amount, preview.fee_paid) == (percent, float(refund), 199.0)
    assert booking_status(db, booking_id) == "CONFIRMED"  # a preview changes nothing

    done = service.cancel(db, world["user"], booking_id, cancel_at)
    assert (done.percent, done.refund_amount, done.reason) == (percent, float(refund), preview.reason)
    row = db.execute(text("SELECT status, refund_amount, cancelled_at, cancel_reason FROM bookings WHERE booking_id = :b"), {"b": booking_id}).one()
    assert (row.status, row.refund_amount, row.cancelled_at, row.cancel_reason) == ("CANCELLED", Decimal(refund), cancel_at, preview.reason)
    payment = db.execute(text("SELECT status, refunded_amount FROM payments WHERE booking_id = :b"), {"b": booking_id}).one()
    assert (payment.status, payment.refunded_amount) == (payment_status, Decimal(refund))


def test_cancelling_a_hold_costs_nothing(db, world):
    booking = hold(db, world)
    assert service.cancel_preview(db, world["user"], booking.booking_id, NOW).refund_amount == 0
    done = service.cancel(db, world["user"], booking.booking_id, NOW + timedelta(minutes=1))
    assert (done.refund_amount, done.fee_paid) == (0, 0)
    assert booking_status(db, booking.booking_id) == "CANCELLED"
    assert hold(db, world, "a", at(12), user="other").status == "HELD"  # the slot is free again


def test_cancelling_a_charge_now_booking_refunds_nothing_because_nothing_was_paid(db, world):
    booking = service.create_instant(db, world["user"], world["a"], None, NOW)
    done = service.cancel(db, world["user"], booking.booking_id, NOW)
    assert (done.refund_amount, done.fee_paid) == (0, 0)


def test_only_held_or_confirmed_bookings_can_be_cancelled_and_only_once(db, world):
    booking_id = confirmed(db, world)
    service.cancel(db, world["user"], booking_id, at(10))
    for call in (service.cancel, service.cancel_preview):
        with pytest.raises(AppError) as error:
            call(db, world["user"], booking_id, at(10))
        assert error.value.code == "CANNOT_CANCEL"
    active = confirmed(db, world, "b")
    db.execute(text("UPDATE bookings SET status = 'ACTIVE' WHERE booking_id = :b"), {"b": active})
    db.commit()
    with pytest.raises(AppError) as error:
        service.cancel(db, world["user"], active, NOW)
    assert error.value.code == "CANNOT_CANCEL"
    with pytest.raises(AppError) as error:
        service.cancel(db, world["other"], booking_id, NOW)
    assert error.value.status_code == 404


def test_a_cancelled_slot_can_be_booked_by_someone_else(db, world):
    booking_id = confirmed(db, world)
    service.cancel(db, world["user"], booking_id, at(10))
    assert hold(db, world, "a", at(12), user="other").status == "HELD"


# ---------------------------------------------------------------- my bookings

def test_upcoming_and_past_scopes(db, world):
    upcoming = confirmed(db, world, "a", at(14))
    expired = make_booking(db, world["a"], at(18), at(19), status="HELD", hold_expires_at=NOW - timedelta(minutes=3), user_id=world["user"])
    service.expire_stale_holds(db, NOW, user_id=world["user"])  # the one-hold rule allows a single HELD row per user
    db.commit()
    held = make_booking(db, world["b"], at(16), at(17), status="HELD", hold_expires_at=NOW + timedelta(minutes=3), user_id=world["user"])
    cancelled = confirmed(db, world, "b", at(20))
    service.cancel(db, world["user"], cancelled, at(10))
    over = make_booking(db, world["a"], at(7), at(8), user_id=world["user"])  # confirmed but already over

    ids = lambda scope: [b.booking_id for b in service.my_bookings(db, world["user"], scope, NOW)]  # noqa: E731
    assert ids("upcoming") == [upcoming, held]                      # soonest first
    assert ids("past") == [cancelled, expired, over]                # most recent first
    statuses = {b.booking_id: b.status for b in service.my_bookings(db, world["user"], "past", NOW)}
    assert statuses[expired] == "EXPIRED" and statuses[cancelled] == "CANCELLED"


def test_unpaid_bills_listing(db, world):
    assert service.unpaid_bills(db, world["user"]).count == 0
    make_due_bill(db, world["user"], world["a"], 100.50)
    make_due_bill(db, world["user"], world["b"], 50)
    dues = service.unpaid_bills(db, world["user"])
    assert (dues.count, dues.total) == (2, 150.5)
    assert dues.items[0].station_name == "Test hub"
    assert service.unpaid_bills(db, world["other"]).count == 0


# ---------------------------------------------------------------- over HTTP (real clock)

def sign_in(user_id):
    app.dependency_overrides[get_current_user] = lambda: User(user_id=user_id, email="driver@test.dev", role="USER")


def future_start(hours=3) -> str:
    return (ceil_to_slot(datetime.now(timezone.utc)) + timedelta(hours=hours)).isoformat()


def test_http_booking_needs_a_login(client):
    for method, path in [("post", "/api/bookings"), ("get", "/api/me/bookings"), ("get", "/api/me/dues"), ("post", "/api/bookings/instant")]:
        assert getattr(client, method)(path).status_code == 401


def test_http_create_hold_and_read_it_back(db_client, world):
    sign_in(world["user"])
    response = db_client.post("/api/bookings", json={"charger_id": str(world["a"]), "start": future_start(), "blocks": 2})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "HELD" and body["booking_fee"] == 199 and body["blocks"] == 2 and body["charger"]["label"] == "A"
    assert db_client.get(f"/api/bookings/{body['booking_id']}").json()["status"] == "HELD"
    assert [b["booking_id"] for b in db_client.get("/api/me/bookings").json()] == [body["booking_id"]]
    assert db_client.get("/api/me/bookings", params={"scope": "past"}).json() == []
    assert db_client.get("/api/me/bookings", params={"scope": "nonsense"}).status_code == 422


def test_http_slot_taken_returns_409_with_alternatives_in_the_error_format(db_client, world):
    start = future_start()
    sign_in(world["other"])
    assert db_client.post("/api/bookings", json={"charger_id": str(world["a"]), "start": start, "blocks": 1}).status_code == 201
    sign_in(world["user"])
    response = db_client.post("/api/bookings", json={"charger_id": str(world["a"]), "start": start, "blocks": 1})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "SLOT_TAKEN" and error["message"]
    assert [c["label"] for c in error["details"]["alternatives"]["other_chargers"]] == ["B"]


def test_http_validation_and_ownership(db_client, world):
    sign_in(world["user"])
    post = lambda **body: db_client.post("/api/bookings", json={"charger_id": str(world["a"]), "start": future_start(), "blocks": 1, **body})  # noqa: E731
    assert post(blocks=5).status_code == 422 and post(blocks=0).status_code == 422
    assert post(start="2020-01-01T10:00:00Z").json()["error"]["code"] == "START_IN_PAST"
    booking_id = post().json()["booking_id"]
    sign_in(world["other"])
    assert db_client.get(f"/api/bookings/{booking_id}").status_code == 404
    assert db_client.post(f"/api/bookings/{booking_id}/cancel").status_code == 404


def test_http_cancel_preview_then_cancel(db_client, world):
    sign_in(world["user"])
    booking_id = db_client.post("/api/bookings", json={"charger_id": str(world["a"]), "start": future_start(), "blocks": 1}).json()["booking_id"]
    assert db_client.get(f"/api/bookings/{booking_id}/cancel-preview").json()["refund_amount"] == 0
    assert db_client.post(f"/api/bookings/{booking_id}/cancel").json()["booking_id"] == booking_id
    assert db_client.get(f"/api/bookings/{booking_id}").json()["status"] == "CANCELLED"
    assert db_client.post(f"/api/bookings/{booking_id}/cancel").json()["error"]["code"] == "CANNOT_CANCEL"


def test_http_charge_now_and_dues(db_client, world):
    sign_in(world["user"])
    response = db_client.post("/api/bookings/instant", json={"charger_id": str(world["a"])})
    assert response.status_code == 201 and len(response.json()["otp"]) == 6 and response.json()["booking_fee"] == 0
    assert "otp" not in db_client.get(f"/api/bookings/{response.json()['booking_id']}").json()
    assert db_client.get("/api/me/dues").json() == {"count": 0, "total": 0, "items": []}
