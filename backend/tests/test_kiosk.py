"""The station kiosk: device keys, the status board, starting with a code, and walk-ins (needs the test database).

Service functions take `now`, so these tests pretend to be at chosen moments of Monday 2026-10-12.
Razorpay is replaced by a fake gateway: nothing here touches the network.
"""

import hashlib
import hmac
import itertools
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.features.bookings import service as bookings
from app.features.bookings.models import Booking
from app.features.jobs.lazy import run_due_jobs
from app.features.kiosk import admin_router, keys, service as kiosk, walkin
from app.features.kiosk.models import AdminAlert, StationDevice
from app.features.kiosk.schemas import WalkInCreate
from app.features.payments import service as payments
from app.features.payments.gateway import get_gateway
from app.features.payments.models import Payment
from app.main import app
from tests import factories
from tests.conftest import needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
M = timedelta(minutes=1)
WEBHOOK_SECRET = "test-razorpay-webhook-secret"
_numbers = itertools.count(1)


# ---------------------------------------------------------------- helpers

pytestmark = needs_db


class FakeGateway:
    """Stands in for Razorpay. `paid` holds the payment ids of links that were paid."""

    def __init__(self):
        self.links = {}
        self.paid = {}
        self.orders = []

    def create_order(self, amount_paise, receipt, notes):
        order_id = f"order_fake_{next(_numbers)}"
        self.orders.append((order_id, amount_paise))
        return order_id

    def create_payment_link(self, amount_paise, reference_id, description, notes):
        link_id = f"plink_fake_{next(_numbers)}"
        self.links[link_id] = {"amount": amount_paise, "reference": reference_id, "notes": notes}
        return link_id, f"https://rzp.test/{link_id}"

    def payment_link_status(self, link_id):
        return ("paid", self.paid[link_id]) if link_id in self.paid else ("created", None)


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


@pytest.fixture(autouse=True)
def clean_polling_memory():
    walkin._last_asked.clear()


@pytest.fixture
def fake():
    return FakeGateway()


@pytest.fixture
def world(db):
    station, other_station = make_station(db, "Kiosk hub", 23.03, 72.55), make_station(db, "Far hub", 23.1, 72.6)
    device, key = admin_router.create_device(db, station, "Entrance kiosk")
    other_device, other_key = admin_router.create_device(db, other_station, "Far kiosk")
    return {
        "station": station, "other_station": other_station,
        "a": make_charger(db, station, "CCS2", 60, 20, label="A"),
        "b": make_charger(db, station, "TYPE2", 22, 18, label="B"),
        "far": make_charger(db, other_station, "CCS2", 60, 20, label="FAR"),
        "device": device, "key": key, "other_device": other_device, "other_key": other_key,
        "user": make_user(db),
    }


def booked(db, world, charger="a", start=NOW, minutes=60, code=True):
    """A confirmed app booking and (when asked) its plain code."""
    booking_id = make_booking(db, world[charger], start, start + minutes * M, user_id=world["user"])
    plain = None
    if code:
        plain = bookings.issue_code(db, db.get(Booking, booking_id))
        db.commit()
    return booking_id, plain


def value(db, sql, **params):
    return db.execute(text(sql), params).scalar_one()


def walk_in(db, world, fake, charger="a", amount=200, until_next=False, now=NOW, device="device"):
    body = WalkInCreate(charger_id=world[charger], amount=None if until_next else amount, until_next=until_next)
    return walkin.create(db, world[device], body, fake, now)


def pay_link(db, fake, out, payment_id=None):
    """The person pays the QR: Razorpay now says the link is paid, and the kiosk's next poll finds out."""
    link = db.query(Payment).filter_by(booking_id=out.walk_in_id).one().provider_order_id
    fake.paid[link] = payment_id or f"pay_{next(_numbers)}"
    return link, fake.paid[link]


# ---------------------------------------------------------------- the status board

def test_the_board_shows_every_charger_of_this_station_only(db, world):
    board = kiosk.status(db, world["device"], NOW)
    assert board.station_name == "Kiosk hub"
    assert [t.label for t in board.chargers] == ["A", "B"]
    assert all(t.state == "FREE" for t in board.chargers)
    assert board.idle_reset_seconds == 30


def test_a_free_charger_says_until_when(db, world):
    booked(db, world, start=NOW + 60 * M)
    a = next(t for t in kiosk.status(db, world["device"], NOW).chargers if t.label == "A")
    assert a.state == "FREE" and a.free_until == NOW + 55 * M  # 5 minutes before the booking
    assert a.can_walk_in
    assert [o.kind for o in a.options] == ["AMOUNT", "AMOUNT", "AMOUNT", "UNTIL_NEXT"]
    assert a.options[-1].until == NOW + 55 * M


def test_a_charger_kept_for_a_booking_shows_when(db, world):
    booked(db, world, start=NOW + 10 * M)
    db.execute(text("SELECT apply_reservation_locks(:now)"), {"now": NOW})
    db.commit()
    a = next(t for t in kiosk.status(db, world["device"], NOW).chargers if t.label == "A")
    assert a.state == "RESERVED" and a.reserved_for == NOW + 10 * M
    assert not a.can_walk_in and a.walk_in_blocked_reason == "BOOKING_SOON"  # only 5 minutes of room


def test_a_broken_charger_is_out_of_service(db, world):
    db.execute(text("SELECT simulate_charger_event(:c, 'FAULT', :now)"), {"c": world["a"], "now": NOW})
    db.commit()
    a = next(t for t in kiosk.status(db, world["device"], NOW).chargers if t.label == "A")
    assert a.state == "OUT_OF_SERVICE" and not a.can_walk_in


def test_a_charging_tile_shows_progress_and_no_person(db, world):
    from app.features.charging import service as charging

    booking_id, _ = booked(db, world)
    charging.start_session(db, booking_id, NOW, actor="ADMIN")
    board = kiosk.status(db, world["device"], NOW + 30 * M)
    a = next(t for t in board.chargers if t.label == "A")
    assert a.state == "CHARGING" and a.progress_percent > 20 and a.ends_at == NOW + 60 * M
    dumped = board.model_dump_json()
    for private in ("email", "phone", "user_id", "booking_id", "bill", "otp"):
        assert private not in dumped


def test_a_pending_walk_in_marks_the_tile_as_paying(db, world, fake):
    walk_in(db, world, fake)
    a = next(t for t in kiosk.status(db, world["device"], NOW).chargers if t.label == "A")
    assert a.state == "PAYING" and not a.can_walk_in


# ---------------------------------------------------------------- starting with a code

def test_the_right_code_starts_the_booking_charger(db, world):
    booking_id, code = booked(db, world)
    out = kiosk.otp_start(db, world["device"], code, NOW)
    assert out.charger_label == "A" and out.connector_type == "CCS2"
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=booking_id) == "ACTIVE"
    assert value(db, "SELECT status FROM chargers WHERE charger_id = :c", c=world["a"]) == "CHARGING"
    assert value(db, "SELECT device_id FROM charging_sessions WHERE session_id = :s", s=out.session_id) == world["device"].device_id
    actor = value(db, "SELECT actor FROM booking_events WHERE booking_id = :b ORDER BY event_id DESC LIMIT 1", b=booking_id)
    assert actor == "DEVICE"


def test_a_code_works_from_15_minutes_before_to_10_minutes_after(db, world):
    _, code = booked(db, world, start=NOW + 15 * M)
    assert kiosk.otp_start(db, world["device"], code, NOW).charger_label == "A"  # exactly 15 minutes before
    _, late = booked(db, world, charger="b", start=NOW - 9 * M)
    assert kiosk.otp_start(db, world["device"], late, NOW).charger_label == "B"  # nine minutes after the start


def test_a_wrong_code_says_how_many_tries_are_left(db, world):
    booked(db, world)
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], "000000", NOW)
    assert (error.value.status_code, error.value.code, error.value.details["tries_left"]) == (400, "WRONG_OTP", 4)
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], "12", NOW)  # not even six digits
    assert error.value.code == "WRONG_OTP" and error.value.details["tries_left"] == 3


def test_a_code_before_its_window_is_refused_and_starts_nothing(db, world):
    booking_id, code = booked(db, world, start=NOW + 16 * M)
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], code, NOW)
    assert error.value.code == "OTP_NOT_VALID_NOW"
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=booking_id) == "CONFIRMED"


def test_a_code_after_its_window_is_refused(db, world):
    _, code = booked(db, world, start=NOW - 11 * M, minutes=120)
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], code, NOW)
    assert error.value.code in ("OTP_NOT_VALID_NOW", "WRONG_OTP")  # the no-show job may already have taken the booking


def test_a_code_can_only_be_used_once(db, world):
    _, code = booked(db, world)
    kiosk.otp_start(db, world["device"], code, NOW)
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], code, NOW + M)
    assert error.value.code == "WRONG_OTP"


def test_a_code_from_another_station_never_matches(db, world):
    _, far_code = booked(db, world, charger="far")
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], far_code, NOW)
    assert error.value.code == "WRONG_OTP"
    assert value(db, "SELECT status FROM chargers WHERE charger_id = :c", c=world["far"]) == "AVAILABLE"


def test_five_wrong_tries_start_a_two_minute_cooldown(db, world):
    _, code = booked(db, world)
    for i in range(4):
        with pytest.raises(AppError) as error:
            kiosk.otp_start(db, world["device"], f"00000{i}", NOW + i * 5 * (M / 60))
        assert error.value.code == "WRONG_OTP"
    with pytest.raises(AppError) as error:  # the fifth
        kiosk.otp_start(db, world["device"], "000009", NOW + 20 * (M / 60))
    assert (error.value.status_code, error.value.code, error.value.details["retry_after_seconds"]) == (429, "OTP_COOLDOWN", 120)

    with pytest.raises(AppError) as error:  # even the right code waits
        kiosk.otp_start(db, world["device"], code, NOW + 50 * (M / 60))
    assert error.value.code == "OTP_COOLDOWN" and 0 < error.value.details["retry_after_seconds"] <= 90

    assert kiosk.otp_start(db, world["device"], code, NOW + 20 * (M / 60) + 2 * M).charger_label == "A"  # after two minutes


def test_the_cooldown_comes_again_after_five_more_wrong_tries(db, world):
    t = NOW
    for block in range(2):
        for _ in range(5):
            with pytest.raises(AppError):
                kiosk.otp_start(db, world["device"], "111111", t)
        assert kiosk.cooldown_left(db, world["device"], t) == 120
        t += 2 * M + 1 * (M / 60)
        assert kiosk.cooldown_left(db, world["device"], t) == 0


def test_a_right_code_resets_the_count(db, world):
    _, code = booked(db, world)
    for _ in range(3):
        with pytest.raises(AppError):
            kiosk.otp_start(db, world["device"], "222222", NOW)
    kiosk.otp_start(db, world["device"], code, NOW)
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], "333333", NOW + M)
    assert error.value.details["tries_left"] == 4  # not 1: the right code wiped the streak


def test_twenty_wrong_tries_in_ten_minutes_raise_one_alert(db, world):
    t = NOW
    for _ in range(4):  # four blocks of five, each followed by its two-minute wait: 20 tries in 6 minutes
        for _ in range(5):
            with pytest.raises(AppError):
                kiosk.otp_start(db, world["device"], "444444", t)
        t += 2 * M + 1 * (M / 60)
    alerts = db.query(AdminAlert).all()
    assert len(alerts) == 1
    assert alerts[0].kind == "KIOSK_OTP_GUESSING" and alerts[0].station_id == world["station"] and alerts[0].details["wrong_tries"] == 20
    for _ in range(5):  # still guessing: no second alert inside the same ten minutes
        with pytest.raises(AppError):
            kiosk.otp_start(db, world["device"], "555555", t)
    assert db.query(AdminAlert).count() == 1


def test_nineteen_wrong_tries_raise_no_alert(db, world):
    t = NOW
    for block in range(4):
        for _ in range(5 if block < 3 else 4):
            with pytest.raises(AppError):
                kiosk.otp_start(db, world["device"], "666666", t)
        t += 2 * M + 1 * (M / 60)
    assert db.query(AdminAlert).count() == 0


def test_the_right_code_on_a_busy_charger_is_not_counted_as_a_guess(db, world):
    booking_id, code = booked(db, world, start=NOW + 10 * M)
    db.execute(text("SELECT simulate_charger_event(:c, 'FAULT', :now)"), {"c": world["a"], "now": NOW})
    db.commit()
    with pytest.raises(AppError) as error:
        kiosk.otp_start(db, world["device"], code, NOW)
    assert error.value.code == "CHARGER_UNAVAILABLE"
    assert kiosk.cooldown_left(db, world["device"], NOW) == 0
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=booking_id) == "CONFIRMED"


# ---------------------------------------------------------------- walk-ins: asking for a charger

def test_a_walk_in_holds_the_charger_for_three_minutes_and_returns_a_payment_link(db, world, fake):
    out = walk_in(db, world, fake, amount=200)
    assert out.status == "WAITING_FOR_PAYMENT" and out.amount == 200 and out.seconds_left == 180
    assert out.payment_url.startswith("https://rzp.test/plink_fake_") and out.charger_label == "A"
    booking = db.get(Booking, out.walk_in_id)
    assert (booking.source, booking.status, booking.user_id, booking.hold_expires_at) == ("WALK_IN", "HELD", None, NOW + 3 * M)
    assert booking.start == NOW and booking.end == NOW + 120 * M  # no booking ahead: the 2-hour maximum
    link = next(iter(fake.links.values()))
    assert link["amount"] == 20000 and link["notes"]["purpose"] == "WALKIN_PREPAID"
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert (payment.purpose, payment.status, float(payment.amount)) == ("WALKIN_PREPAID", "CREATED", 200.0)


def test_until_the_next_booking_is_priced_by_the_server(db, world, fake):
    booked(db, world, start=NOW + 65 * M)
    out = walk_in(db, world, fake, until_next=True)
    # The window is 60 minutes (to 5 minutes before the booking): 60 kW x 0.9 x 1 h = 54 kWh, but the default battery takes 32.
    assert out.amount == 640
    assert db.get(Booking, out.walk_in_id).end == NOW + 60 * M


def test_a_walk_in_cannot_overlap_an_upcoming_booking(db, world, fake):
    booked(db, world, start=NOW + 40 * M)
    out = walk_in(db, world, fake)
    assert db.get(Booking, out.walk_in_id).end == NOW + 35 * M  # stops 5 minutes before the booking
    # and the other way round: while the QR is on screen nobody can book the same charger
    with pytest.raises(AppError) as error:
        bookings.create_hold(db, world["user"], world["a"], NOW + 30 * M, 1, None, NOW + M)
    assert error.value.code == "SLOT_TAKEN"


def test_a_walk_in_is_refused_when_the_next_booking_is_too_close(db, world, fake):
    booked(db, world, start=NOW + 15 * M)  # 10 minutes of room after the 5-minute buffer, under the 15-minute minimum
    with pytest.raises(AppError) as error:
        walk_in(db, world, fake)
    assert error.value.code == "NO_ROOM_FOR_WALK_IN"
    assert db.query(Booking).filter_by(source="WALK_IN").count() == 0


def test_a_walk_in_is_refused_on_a_charger_that_is_booked_right_now(db, world, fake):
    booked(db, world, start=NOW - 5 * M)
    with pytest.raises(AppError) as error:
        walk_in(db, world, fake)
    assert error.value.code == "CHARGER_BUSY"


def test_only_one_walk_in_can_hold_a_charger(db, world, fake):
    walk_in(db, world, fake)
    with pytest.raises(AppError) as error:
        walk_in(db, world, fake, now=NOW + M)
    assert error.value.code == "CHARGER_BUSY"


def test_a_device_cannot_take_another_stations_charger(db, world, fake):
    with pytest.raises(AppError) as error:
        walk_in(db, world, fake, charger="far")
    assert (error.value.status_code, error.value.code) == (404, "CHARGER_NOT_FOUND")
    assert not fake.links


def test_the_amount_must_be_one_of_the_offered_ones(db, world, fake):
    for bad in (150, 1, 100000):
        with pytest.raises(AppError) as error:
            walk_in(db, world, fake, amount=bad)
        assert error.value.code == "INVALID_AMOUNT"
    with pytest.raises(AppError):
        walkin.create(db, world["device"], WalkInCreate(charger_id=world["a"]), fake, NOW)  # neither an amount nor "until next"
    with pytest.raises(AppError):
        walkin.create(db, world["device"], WalkInCreate(charger_id=world["a"], amount=100, until_next=True), fake, NOW)  # both
    assert not fake.links


def test_a_charger_without_a_price_cannot_take_a_walk_in(db, world, fake):
    free = make_charger(db, world["station"], "CCS2", 60, None, label="NOPRICE")
    world["free"] = free
    with pytest.raises(AppError) as error:
        walk_in(db, world, fake, charger="free")
    assert error.value.code == "PRICE_UNKNOWN"
    tile = next(t for t in kiosk.status(db, world["device"], NOW).chargers if t.label == "NOPRICE")
    assert not tile.can_walk_in and tile.walk_in_blocked_reason == "PRICE_UNKNOWN" and tile.options == []


def test_a_broken_charger_and_a_charging_one_are_refused(db, world, fake):
    db.execute(text("SELECT simulate_charger_event(:c, 'FAULT', :now)"), {"c": world["a"], "now": NOW})
    db.execute(text("SELECT simulate_charger_event(:c, 'EXTERNAL_START', :now)"), {"c": world["b"], "now": NOW})
    db.commit()
    with pytest.raises(AppError) as error:
        walk_in(db, world, fake, charger="a")
    assert error.value.code == "CHARGER_UNAVAILABLE"
    with pytest.raises(AppError) as error:
        walk_in(db, world, fake, charger="b")
    assert error.value.code == "CHARGER_BUSY"


def test_if_the_payment_service_is_down_the_charger_is_freed(db, world):
    class Down(FakeGateway):
        def create_payment_link(self, *args, **kwargs):
            raise AppError(502, "PAYMENT_PROVIDER_ERROR", "The payment service is not responding. Please try again.")

    with pytest.raises(AppError) as error:
        walk_in(db, world, Down())
    assert error.value.code == "PAYMENT_PROVIDER_ERROR"
    assert value(db, "SELECT status FROM bookings WHERE source = 'WALK_IN'") == "CANCELLED"
    assert walk_in(db, world, FakeGateway(), now=NOW + M).status == "WAITING_FOR_PAYMENT"  # the charger can be taken again


# ---------------------------------------------------------------- walk-ins: paying, waiting, backing out

def test_an_unpaid_walk_in_expires_after_three_minutes_and_frees_the_charger(db, world, fake):
    out = walk_in(db, world, fake)
    still = walkin.get(db, world["device"], out.walk_in_id, fake, NOW + timedelta(seconds=179))
    assert still.status == "WAITING_FOR_PAYMENT" and still.seconds_left == 1
    gone = walkin.get(db, world["device"], out.walk_in_id, fake, NOW + timedelta(seconds=181))
    assert gone.status == "EXPIRED" and gone.payment_url is None
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=out.walk_in_id) == "EXPIRED"
    assert walk_in(db, world, fake, now=NOW + 4 * M).status == "WAITING_FOR_PAYMENT"  # free for the next person


def test_backing_out_frees_the_charger_at_once(db, world, fake):
    out = walk_in(db, world, fake)
    result = walkin.cancel(db, world["device"], out.walk_in_id, NOW + 20 * (M / 60))
    assert result.status == "CANCELLED"
    assert walk_in(db, world, fake, now=NOW + 30 * (M / 60)).status == "WAITING_FOR_PAYMENT"


def test_paying_starts_charging_with_the_prepaid_amount(db, world, fake):
    out = walk_in(db, world, fake, amount=200)
    pay_link(db, fake, out)
    status = walkin.get(db, world["device"], out.walk_in_id, fake, NOW + 30 * (M / 60))
    assert status.status == "PAID" and status.session_id is not None and status.payment_url is None
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=out.walk_in_id) == "ACTIVE"
    assert value(db, "SELECT status FROM chargers WHERE charger_id = :c", c=world["a"]) == "CHARGING"
    session = db.execute(text("SELECT source, prepaid_amount, started_at, booking_id FROM charging_sessions WHERE session_id = :s"), {"s": status.session_id}).one()
    assert (session.source, float(session.prepaid_amount), session.started_at, session.booking_id) == ("WALK_IN", 200.0, NOW + 30 * (M / 60), out.walk_in_id)
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert payment.status == "CAPTURED" and payment.session_id == status.session_id and payment.provider_payment_id.startswith("pay_")
    a = next(t for t in kiosk.status(db, world["device"], NOW + M).chargers if t.label == "A")
    assert a.state == "CHARGING" and a.walk_in.prepaid == 200


def test_the_polling_fallback_pays_once_even_when_asked_twice(db, world, fake):
    out = walk_in(db, world, fake)
    pay_link(db, fake, out)
    walkin.get(db, world["device"], out.walk_in_id, fake, NOW + 10 * (M / 60))
    walkin._last_asked.clear()
    walkin.get(db, world["device"], out.walk_in_id, fake, NOW + 20 * (M / 60))
    assert db.query(Payment).filter_by(booking_id=out.walk_in_id, status="CAPTURED").count() == 1
    assert value(db, "SELECT count(*) FROM charging_sessions WHERE booking_id = :b", b=out.walk_in_id) == 1


def _link_paid_body(link_id, payment_id, event="payment_link.paid"):
    return json.dumps(
        {"event": event, "payload": {"payment_link": {"entity": {"id": link_id}}, "payment": {"entity": {"id": payment_id, "status": "captured"}}}}
    ).encode()


def _deliver(db, body, event_id, now=NOW):
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return payments.handle_webhook(db, body, signature, event_id, now)


def test_the_payment_link_webhook_starts_charging_once(db, world, fake):
    out = walk_in(db, world, fake)
    link = db.query(Payment).filter_by(booking_id=out.walk_in_id).one().provider_order_id
    body = _link_paid_body(link, "pay_hook_1")
    assert _deliver(db, body, "evt_1", NOW + 20 * (M / 60)) == "processed"
    assert _deliver(db, body, "evt_1", NOW + 21 * (M / 60)) == "duplicate"
    assert _deliver(db, body, "evt_other_id_same_payment", NOW + 22 * (M / 60)) == "processed"  # a different event for a paid link changes nothing
    assert value(db, "SELECT count(*) FROM charging_sessions WHERE booking_id = :b", b=out.walk_in_id) == 1
    assert value(db, "SELECT status FROM chargers WHERE charger_id = :c", c=world["a"]) == "CHARGING"


def test_a_webhook_for_an_unknown_link_is_ignored(db, world):
    assert _deliver(db, _link_paid_body("plink_nobody", "pay_x"), "evt_unknown") == "ignored"
    assert db.query(Payment).count() == 0


def test_a_payment_that_arrives_after_the_hold_ran_out_is_refunded_in_full(db, world, fake):
    out = walk_in(db, world, fake, amount=200)
    run_due_jobs(db, NOW + 4 * M, world["station"])  # the hold has expired
    link = db.query(Payment).filter_by(booking_id=out.walk_in_id).one().provider_order_id
    assert _deliver(db, _link_paid_body(link, "pay_late"), "evt_late", NOW + 5 * M) == "processed"
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert (payment.status, float(payment.refunded_amount)) == ("REFUNDED", 200.0)
    assert value(db, "SELECT count(*) FROM charging_sessions WHERE booking_id = :b", b=out.walk_in_id) == 0
    assert value(db, "SELECT status FROM chargers WHERE charger_id = :c", c=world["a"]) == "AVAILABLE"
    status = walkin.get(db, world["device"], out.walk_in_id, fake, NOW + 6 * M)
    assert status.status == "EXPIRED" and status.refunded == 200


def test_a_payment_after_backing_out_is_refunded_in_full(db, world, fake):
    out = walk_in(db, world, fake)
    walkin.cancel(db, world["device"], out.walk_in_id, NOW + 10 * (M / 60))
    link = db.query(Payment).filter_by(booking_id=out.walk_in_id).one().provider_order_id
    _deliver(db, _link_paid_body(link, "pay_after_cancel"), "evt_cancel", NOW + 20 * (M / 60))
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert (payment.status, float(payment.refunded_amount)) == ("REFUNDED", 200.0)
    assert value(db, "SELECT count(*) FROM charging_sessions WHERE booking_id = :b", b=out.walk_in_id) == 0
    assert walkin.get(db, world["device"], out.walk_in_id, fake, NOW + 30 * (M / 60)).status == "CANCELLED"


def test_if_the_charger_breaks_while_they_pay_the_money_goes_back(db, world, fake):
    out = walk_in(db, world, fake, amount=500)
    db.execute(text("SELECT simulate_charger_event(:c, 'FAULT', :now)"), {"c": world["a"], "now": NOW + 10 * (M / 60)})
    db.commit()
    link = db.query(Payment).filter_by(booking_id=out.walk_in_id).one().provider_order_id
    _deliver(db, _link_paid_body(link, "pay_broke"), "evt_broke", NOW + 30 * (M / 60))
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert (payment.status, float(payment.refunded_amount)) == ("REFUNDED", 500.0)
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=out.walk_in_id) == "EXPIRED"


def test_another_stations_kiosk_cannot_see_or_cancel_a_walk_in(db, world, fake):
    out = walk_in(db, world, fake)
    with pytest.raises(AppError) as error:
        walkin.get(db, world["other_device"], out.walk_in_id, fake, NOW)
    assert (error.value.status_code, error.value.code) == (404, "WALK_IN_NOT_FOUND")
    with pytest.raises(AppError):
        walkin.cancel(db, world["other_device"], out.walk_in_id, NOW)
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=out.walk_in_id) == "HELD"


def test_an_app_booking_is_not_a_walk_in(db, world, fake):
    booking_id, _ = booked(db, world)
    with pytest.raises(AppError) as error:
        walkin.get(db, world["device"], booking_id, fake, NOW)
    assert error.value.code == "WALK_IN_NOT_FOUND"


# ---------------------------------------------------------------- walk-ins: settling

def _start_paid_walk_in(db, world, fake, amount=200, charger="a", start=NOW):
    out = walk_in(db, world, fake, amount=amount, charger=charger, now=start)
    link, payment_id = pay_link(db, fake, out)
    status = walkin.get(db, world["device"], out.walk_in_id, fake, start)
    assert status.status == "PAID"
    return out, status


def test_unplugging_early_bills_what_was_used_and_records_the_refund(db, world, fake):
    out, status = _start_paid_walk_in(db, world, fake, amount=200)
    # 60 kW x 0.9 x 6 minutes = 5.4 kWh x Rs 20 = Rs 108; Rs 92 of the Rs 200 comes back.
    result = db.execute(text("SELECT simulate_charger_event(:c, 'UNPLUG', :now)"), {"c": world["a"], "now": NOW + 6 * M}).scalar_one()
    db.commit()
    assert result["accepted"] is True
    session = db.execute(text("SELECT bill_amount, bill_status, end_reason, energy_kwh FROM charging_sessions WHERE session_id = :s"), {"s": status.session_id}).one()
    assert (float(session.bill_amount), session.bill_status, session.end_reason, float(session.energy_kwh)) == (108.0, "PREPAID_SETTLED", "UNPLUGGED", 5.4)
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert (payment.status, float(payment.refunded_amount)) == ("PARTIALLY_REFUNDED", 92.0)
    assert float(value(db, "SELECT refund_amount FROM bookings WHERE booking_id = :b", b=out.walk_in_id)) == 92.0
    assert value(db, "SELECT status FROM bookings WHERE booking_id = :b", b=out.walk_in_id) == "COMPLETED"
    assert value(db, "SELECT status FROM chargers WHERE charger_id = :c", c=world["a"]) == "AVAILABLE"


def test_the_tile_shows_used_and_refunded_for_two_minutes(db, world, fake):
    _start_paid_walk_in(db, world, fake, amount=200)
    db.execute(text("SELECT simulate_charger_event(:c, 'UNPLUG', :now)"), {"c": world["a"], "now": NOW + 6 * M})
    db.commit()
    tile = next(t for t in kiosk.status(db, world["device"], NOW + 7 * M).chargers if t.label == "A")
    assert tile.state == "FREE" and (tile.last_walk_in.used, tile.last_walk_in.refunded) == (108.0, 92.0)
    later = next(t for t in kiosk.status(db, world["device"], NOW + 6 * M + 121 * (M / 60)).chargers if t.label == "A")
    assert later.last_walk_in is None


def test_charging_stops_when_the_prepaid_money_is_used_up(db, world, fake):
    out, status = _start_paid_walk_in(db, world, fake, amount=200)
    run_due_jobs(db, NOW + 11 * M, world["station"])  # Rs 200 = 10 kWh = 11.1 minutes at 54 kW: not yet
    assert value(db, "SELECT ended_at IS NULL FROM charging_sessions WHERE session_id = :s", s=status.session_id) is True
    run_due_jobs(db, NOW + 13 * M, world["station"])
    session = db.execute(text("SELECT bill_amount, end_reason, energy_kwh FROM charging_sessions WHERE session_id = :s"), {"s": status.session_id}).one()
    assert session.end_reason == "PREPAID_USED"
    assert float(session.bill_amount) == 200.0 and float(session.energy_kwh) == 10.0  # never more than they paid for
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert (payment.status, float(payment.refunded_amount)) == ("CAPTURED", 0.0)  # nothing left over to refund


def test_charging_stops_before_the_next_booking(db, world, fake):
    booked(db, world, charger="b", start=NOW + 40 * M)
    out, status = _start_paid_walk_in(db, world, fake, amount=500, charger="b")  # Rs 500 would last 84 minutes at 22 kW
    run_due_jobs(db, NOW + 36 * M, world["station"])
    session = db.execute(text("SELECT ended_at, end_reason, bill_amount FROM charging_sessions WHERE session_id = :s"), {"s": status.session_id}).one()
    assert session.end_reason == "NEXT_BOOKING_AUTO_STOP" and session.ended_at == NOW + 35 * M
    assert float(session.bill_amount) == 207.9  # 22 kW x 0.9 x 35 min = 11.55 kWh x Rs 18
    payment = db.query(Payment).filter_by(booking_id=out.walk_in_id).one()
    assert (payment.status, float(payment.refunded_amount)) == ("PARTIALLY_REFUNDED", 292.1)


def test_charging_stops_when_the_walk_in_window_ends(db, world, fake):
    world["slow"] = make_charger(db, world["station"], "TYPE2", 7, 5, label="SLOW")  # 6.3 kW at Rs 5: Rs 500 would last for hours
    out, status = _start_paid_walk_in(db, world, fake, amount=500, charger="slow")
    run_due_jobs(db, NOW + 125 * M, world["station"])
    session = db.execute(text("SELECT ended_at, end_reason, bill_amount FROM charging_sessions WHERE session_id = :s"), {"s": status.session_id}).one()
    assert session.end_reason == "SLOT_END_AUTO_STOP" and session.ended_at == NOW + 120 * M  # the 2-hour maximum
    assert float(session.bill_amount) == 63.0  # 6.3 kW x 2 h = 12.6 kWh x Rs 5
    assert float(db.query(Payment).filter_by(booking_id=out.walk_in_id).one().refunded_amount) == 437.0
    assert value(db, "SELECT status FROM chargers WHERE charger_id = :c", c=world["slow"]) == "AVAILABLE"


def test_settling_twice_changes_nothing(db, world, fake):
    out, status = _start_paid_walk_in(db, world, fake, amount=200)
    for at in (6, 7):
        db.execute(
            text("SELECT finish_session(CAST(:s AS uuid), CAST(:at AS timestamptz), 'ADMIN', 'ADMIN', CAST(:at AS timestamptz))"),
            {"s": status.session_id, "at": NOW + at * M},
        )
    db.commit()
    assert float(db.query(Payment).filter_by(booking_id=out.walk_in_id).one().refunded_amount) == 92.0


# ---------------------------------------------------------------- the device key over HTTP

@pytest.fixture
def api(db_client, fake):
    app.dependency_overrides[get_gateway] = lambda: fake
    return db_client


def test_http_a_kiosk_needs_a_valid_key(api, world):
    assert api.get("/api/kiosk/status").json()["error"]["code"] == "INVALID_DEVICE_KEY"
    assert api.get("/api/kiosk/status", headers={"X-Device-Key": "ks_nothing_here"}).status_code == 401
    assert api.get("/api/kiosk/status", headers={"X-Device-Key": world["key"] + "0"}).status_code == 401
    ok = api.get("/api/kiosk/status", headers={"X-Device-Key": world["key"]})
    assert ok.status_code == 200 and ok.json()["station_name"] == "Kiosk hub"


def test_http_a_key_only_opens_its_own_station(api, world):
    a = api.get("/api/kiosk/status", headers={"X-Device-Key": world["key"]}).json()
    b = api.get("/api/kiosk/status", headers={"X-Device-Key": world["other_key"]}).json()
    assert {c["label"] for c in a["chargers"]} == {"A", "B"} and {c["label"] for c in b["chargers"]} == {"FAR"}


def test_http_a_switched_off_kiosk_is_refused(api, world, db):
    world["device"].is_active = False
    db.commit()
    response = api.get("/api/kiosk/status", headers={"X-Device-Key": world["key"]})
    assert (response.status_code, response.json()["error"]["code"]) == (403, "DEVICE_DISABLED")


def test_http_the_kiosk_remembers_when_it_was_last_seen(api, world, db):
    api.get("/api/kiosk/status", headers={"X-Device-Key": world["key"]})
    db.refresh(world["device"])
    assert world["device"].last_seen_at is not None


def test_http_a_walk_in_end_to_end(api, world, db, fake):
    headers = {"X-Device-Key": world["key"]}
    created = api.post("/api/kiosk/walk-ins", json={"charger_id": str(world["a"]), "amount": 100}, headers=headers)
    assert created.status_code == 201 and created.json()["status"] == "WAITING_FOR_PAYMENT"
    walk_in_id = created.json()["walk_in_id"]
    assert api.get(f"/api/kiosk/walk-ins/{walk_in_id}", headers=headers).json()["status"] == "WAITING_FOR_PAYMENT"
    link = db.query(Payment).filter_by(purpose="WALKIN_PREPAID").one().provider_order_id
    fake.paid[link] = "pay_http_walkin"
    walkin._last_asked.clear()
    assert api.get(f"/api/kiosk/walk-ins/{walk_in_id}", headers=headers).json()["status"] == "PAID"
    assert api.get(f"/api/kiosk/walk-ins/{walk_in_id}", headers={"X-Device-Key": world["other_key"]}).status_code == 404


def test_http_a_wrong_code_and_the_cooldown(api, world):
    headers = {"X-Device-Key": world["key"]}
    first = api.post("/api/kiosk/otp-start", json={"otp": "000000"}, headers=headers)
    assert (first.status_code, first.json()["error"]["code"], first.json()["error"]["details"]["tries_left"]) == (400, "WRONG_OTP", 4)
    for _ in range(4):
        last = api.post("/api/kiosk/otp-start", json={"otp": "000000"}, headers=headers)
    assert (last.status_code, last.json()["error"]["code"]) == (429, "OTP_COOLDOWN")
    assert api.post("/api/kiosk/otp-start", json={"otp": "000000"}, headers=headers).json()["error"]["details"]["retry_after_seconds"] > 0


def test_http_admin_creates_a_key_that_works(db_client, world, db):
    from app.features.auth.dependencies import get_current_user
    from app.features.auth.models import User

    app.dependency_overrides[get_current_user] = lambda: User(user_id=world["user"], email="admin@test.dev", role="ADMIN")
    created = db_client.post(f"/api/admin/stations/{world['station']}/devices", json={"name": "Second kiosk"})
    assert created.status_code == 201
    body = created.json()
    assert body["key"].startswith("ks_") and body["name"] == "Second kiosk"
    stored = db.get(StationDevice, UUID(body["device_id"]))
    assert stored.api_key_hash == keys.hash_key(body["key"]) and body["key"] not in stored.api_key_hash
    assert db_client.get("/api/kiosk/status", headers={"X-Device-Key": body["key"]}).status_code == 200
    listing = db_client.get(f"/api/admin/stations/{world['station']}/devices").json()
    assert len(listing) == 2 and all("key" not in d and "api_key_hash" not in d for d in listing)
    assert db_client.post(f"/api/admin/devices/{body['device_id']}/disable").json()["is_active"] is False
    assert db_client.get("/api/kiosk/status", headers={"X-Device-Key": body["key"]}).status_code == 403
    assert db_client.post("/api/admin/stations/00000000-0000-0000-0000-000000000000/devices", json={"name": "x"}).status_code == 404


def test_http_only_admins_can_make_keys(db_client, world):
    assert db_client.post(f"/api/admin/stations/{world['station']}/devices", json={"name": "x"}).status_code == 403
