"""Paying the energy bill after charging, and the receipt (needs the test database).

A session is made the real way (confirmed booking -> start -> stop) so the bill is the server's own number.
"""

import hashlib
import hmac
import itertools
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.bookings import service as bookings
from app.features.charging import receipt, service as charging
from app.features.payments import service as payments
from app.features.payments.gateway import get_gateway
from app.features.payments.models import Payment
from app.features.payments.schemas import VerifyRequest
from app.main import app
from tests import factories
from tests.conftest import needs_db

pytestmark = needs_db

KEY_SECRET = "test-razorpay-key-secret"
WEBHOOK_SECRET = "test-razorpay-webhook-secret"
START = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
M = timedelta(minutes=1)
_numbers = itertools.count(1)


class FakeGateway:
    def __init__(self):
        self.orders = []

    def create_order(self, amount_paise, receipt, notes):
        order_id = f"order_bill_{next(_numbers)}"
        self.orders.append((order_id, amount_paise, notes))
        return order_id


def sign(order_id, payment_id):
    return hmac.new(KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


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
def fake():
    return FakeGateway()


@pytest.fixture
def world(db):
    station = make_station(db, "Bill hub", 23.03, 72.55)
    user, other = make_user(db), make_user(db)
    charger = make_charger(db, station, "CCS2", 60, 20, label="A")
    vehicle = db.execute(
        text("INSERT INTO vehicles (user_id, nickname, connector_type, battery_kwh) VALUES (:u, 'Car', 'CCS2', 100) RETURNING vehicle_id"),
        {"u": user},
    ).scalar_one()
    db.commit()
    return {"station": station, "charger": charger, "user": user, "other": other, "vehicle": vehicle}


def finished_session(db, world, minutes=30):
    """A stopped session with a bill: 60 kW x 0.9 x 30 min = 27 kWh x Rs 20 = Rs 540."""
    booking_id = make_booking(db, world["charger"], START, START + 60 * M, user_id=world["user"])
    db.execute(text("UPDATE bookings SET vehicle_id = :v WHERE booking_id = :b"), {"v": world["vehicle"], "b": booking_id})
    db.commit()
    session = charging.start_session(db, booking_id, START, actor="ADMIN")
    charging.stop_session(db, world["user"], session.session_id, START + minutes * M)
    return session.session_id


def bill_status(db, session_id):
    return db.execute(text("SELECT bill_status FROM charging_sessions WHERE session_id = :s"), {"s": session_id}).scalar_one()


def pay(db, world, session_id, fake, payment_id=None):
    order = payments.create_energy_order(db, world["user"], session_id, fake)
    payment_id = payment_id or f"pay_{next(_numbers)}"
    request = VerifyRequest(razorpay_order_id=order.order_id, razorpay_payment_id=payment_id, razorpay_signature=sign(order.order_id, payment_id))
    return order, payments.verify_energy(db, world["user"], session_id, request, START + 40 * M), payment_id


# ---------------------------------------------------------------- the order

def test_the_order_is_for_the_servers_bill(db, world, fake):
    session_id = finished_session(db, world)
    assert bill_status(db, session_id) == "DUE"
    order = payments.create_energy_order(db, world["user"], session_id, fake)
    assert (order.amount, order.amount_paise, order.currency, order.key_id) == (540.0, 54000, "INR", "rzp_test_unit")
    assert fake.orders[0][1:] == (54000, {"purpose": "ENERGY", "session_id": str(session_id)})
    payment = db.query(Payment).filter_by(session_id=session_id).one()
    assert (payment.purpose, payment.status, float(payment.amount)) == ("ENERGY", "CREATED", 540.0)


def test_asking_again_returns_the_same_order(db, world, fake):
    session_id = finished_session(db, world)
    first = payments.create_energy_order(db, world["user"], session_id, fake)
    second = payments.create_energy_order(db, world["user"], session_id, fake)
    assert first.order_id == second.order_id and len(fake.orders) == 1


def test_nothing_to_pay_while_charging_is_still_going(db, world, fake):
    booking_id = make_booking(db, world["charger"], START, START + 60 * M, user_id=world["user"])
    session = charging.start_session(db, booking_id, START, actor="ADMIN")
    with pytest.raises(AppError) as error:
        payments.create_energy_order(db, world["user"], session.session_id, fake)
    assert error.value.code == "SESSION_NOT_ENDED"


def test_only_the_owner_can_pay_a_bill(db, world, fake):
    session_id = finished_session(db, world)
    with pytest.raises(AppError) as error:
        payments.create_energy_order(db, world["other"], session_id, fake)
    assert (error.value.status_code, error.value.code) == (404, "SESSION_NOT_FOUND")
    with pytest.raises(AppError):
        payments.create_energy_order(db, world["user"], "00000000-0000-0000-0000-000000000000", fake)
    assert not fake.orders


def test_a_payment_provider_failure_is_a_502_and_leaves_the_bill_due(db, world):
    class Down:
        def create_order(self, *args, **kwargs):
            raise AppError(502, "PAYMENT_PROVIDER_ERROR", "The payment service is not responding. Please try again.")

    session_id = finished_session(db, world)
    with pytest.raises(AppError) as error:
        payments.create_energy_order(db, world["user"], session_id, Down())
    assert error.value.status_code == 502 and bill_status(db, session_id) == "DUE"


# ---------------------------------------------------------------- paying

def test_paying_marks_the_bill_paid_and_clears_the_dues(db, world, fake):
    session_id = finished_session(db, world)
    assert bookings.unpaid_bills(db, world["user"]).count == 1
    _, live, payment_id = pay(db, world, session_id, fake)
    assert live.bill_status == "PAID" and live.bill_amount == 540.0
    assert bill_status(db, session_id) == "PAID"
    assert db.execute(text("SELECT paid_at FROM charging_sessions WHERE session_id = :s"), {"s": session_id}).scalar_one() == START + 40 * M
    payment = db.query(Payment).filter_by(session_id=session_id).one()
    assert (payment.status, payment.provider_payment_id) == ("CAPTURED", payment_id)
    assert bookings.unpaid_bills(db, world["user"]).count == 0


def test_dues_block_new_bookings_until_paid(db, world, fake):
    session_id = finished_session(db, world)
    with pytest.raises(AppError) as error:
        bookings.create_hold(db, world["user"], world["charger"], START + 3 * 60 * M, 1, None, START + 40 * M)
    assert error.value.code == "UNPAID_BILL"
    pay(db, world, session_id, fake)
    assert bookings.create_hold(db, world["user"], world["charger"], START + 3 * 60 * M, 1, None, START + 41 * M).status == "HELD"


def test_a_forged_signature_pays_nothing(db, world, fake):
    session_id = finished_session(db, world)
    order = payments.create_energy_order(db, world["user"], session_id, fake)
    bad = VerifyRequest(razorpay_order_id=order.order_id, razorpay_payment_id="pay_forged", razorpay_signature="0" * 64)
    with pytest.raises(AppError) as error:
        payments.verify_energy(db, world["user"], session_id, bad, START + 40 * M)
    assert error.value.code == "INVALID_SIGNATURE" and bill_status(db, session_id) == "DUE"


def test_a_paid_bill_cannot_be_charged_again(db, world, fake):
    session_id = finished_session(db, world)
    pay(db, world, session_id, fake)
    with pytest.raises(AppError) as error:
        payments.create_energy_order(db, world["user"], session_id, fake)
    assert error.value.code == "BILL_ALREADY_PAID"


def test_verifying_twice_is_harmless(db, world, fake):
    session_id = finished_session(db, world)
    order, live, payment_id = pay(db, world, session_id, fake)
    again = VerifyRequest(razorpay_order_id=order.order_id, razorpay_payment_id=payment_id, razorpay_signature=sign(order.order_id, payment_id))
    assert payments.verify_energy(db, world["user"], session_id, again, START + 50 * M).bill_status == "PAID"
    assert db.execute(text("SELECT paid_at FROM charging_sessions WHERE session_id = :s"), {"s": session_id}).scalar_one() == START + 40 * M


def test_an_order_cannot_be_used_for_another_session_or_user(db, world, fake):
    session_id = finished_session(db, world)
    order = payments.create_energy_order(db, world["user"], session_id, fake)
    request = VerifyRequest(razorpay_order_id=order.order_id, razorpay_payment_id="pay_x", razorpay_signature=sign(order.order_id, "pay_x"))
    with pytest.raises(AppError) as error:
        payments.verify_energy(db, world["other"], session_id, request, START + 40 * M)
    assert error.value.code == "PAYMENT_NOT_FOUND"
    with pytest.raises(AppError):
        payments.verify_energy(db, world["user"], "00000000-0000-0000-0000-000000000000", request, START + 40 * M)
    assert bill_status(db, session_id) == "DUE"


def _captured_webhook(order_id, payment_id):
    return json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id}}}}).encode()


def _deliver(db, body, event_id):
    return payments.handle_webhook(db, body, hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest(), event_id, START + 41 * M)


def test_the_webhook_pays_the_bill_if_the_browser_never_reports_back(db, world, fake):
    session_id = finished_session(db, world)
    order = payments.create_energy_order(db, world["user"], session_id, fake)
    assert _deliver(db, _captured_webhook(order.order_id, "pay_hook"), "evt_bill") == "processed"
    assert bill_status(db, session_id) == "PAID"
    assert _deliver(db, _captured_webhook(order.order_id, "pay_hook"), "evt_bill") == "duplicate"


def test_paying_twice_sends_the_second_payment_back(db, world, fake):
    session_id = finished_session(db, world)
    order = payments.create_energy_order(db, world["user"], session_id, fake)
    db.execute(text("UPDATE charging_sessions SET bill_status = 'PAID' WHERE session_id = :s"), {"s": session_id})  # paid some other way meanwhile
    db.commit()
    _deliver(db, _captured_webhook(order.order_id, "pay_dup"), "evt_dup")
    payment = db.query(Payment).filter_by(session_id=session_id).one()
    assert (payment.status, float(payment.refunded_amount)) == ("REFUNDED", 540.0)


# ---------------------------------------------------------------- the receipt

def test_the_receipt_of_an_unpaid_bill_says_due(db, world):
    session_id = finished_session(db, world)
    r = receipt.get_receipt(db, world["user"], session_id, START + 40 * M)
    assert (r.bill_status, r.total, r.energy_kwh, r.price_per_kwh, r.payment_reference, r.paid_at) == ("DUE", 540.0, 27.0, 20.0, None, None)
    assert (r.station_name, r.charger_label, r.connector_type, r.duration_minutes) == ("Bill hub", "A", "CCS2", 30.0)


def test_the_receipt_of_a_paid_bill_has_the_payment_id(db, world, fake):
    session_id = finished_session(db, world)
    pay(db, world, session_id, fake, payment_id="pay_receipt_1")
    r = receipt.get_receipt(db, world["user"], session_id, START + 45 * M)
    assert (r.bill_status, r.total, r.payment_reference, r.paid_at) == ("PAID", 540.0, "pay_receipt_1", START + 40 * M)
    assert (r.started_at, r.ended_at) == (START, START + 30 * M)


def test_the_receipt_includes_the_booking_fee_when_one_was_paid(db, world, fake):
    session_id = finished_session(db, world)
    booking_id = db.execute(text("SELECT booking_id FROM charging_sessions WHERE session_id = :s"), {"s": session_id}).scalar_one()
    db.execute(
        text("INSERT INTO payments (booking_id, purpose, provider_order_id, amount, status) VALUES (:b, 'BOOKING_FEE', 'order_fee_1', 199, 'CAPTURED')"),
        {"b": booking_id},
    )
    db.commit()
    assert receipt.get_receipt(db, world["user"], session_id, START + 40 * M).booking_fee == 199.0


def test_no_receipt_while_charging_and_none_for_other_drivers(db, world):
    booking_id = make_booking(db, world["charger"], START, START + 60 * M, user_id=world["user"])
    running = charging.start_session(db, booking_id, START, actor="ADMIN")
    with pytest.raises(AppError) as error:
        receipt.get_receipt(db, world["user"], running.session_id, START + 5 * M)
    assert error.value.code == "SESSION_NOT_ENDED"
    other_session = finished_session(db, {**world, "charger": make_charger(db, world["station"], "CCS2", 60, 20, label="B")})
    with pytest.raises(AppError) as error:
        receipt.get_receipt(db, world["other"], other_session, START + 40 * M)
    assert error.value.status_code == 404


# ---------------------------------------------------------------- over HTTP

@pytest.fixture
def api(db_client, world, fake):
    app.dependency_overrides[get_gateway] = lambda: fake
    app.dependency_overrides[get_current_user] = lambda: User(user_id=world["user"], email="driver@test.dev", role="USER")
    return db_client


def test_http_pay_the_bill_and_open_the_receipt(api, world, db):
    # HTTP uses the real clock, so build the finished session relative to now.
    now = datetime.now(timezone.utc)
    booking_id = make_booking(db, world["charger"], now - 90 * M, now - 30 * M, user_id=world["user"])
    session = charging.start_session(db, booking_id, now - 80 * M, actor="ADMIN")
    charging.stop_session(db, world["user"], session.session_id, now - 50 * M)  # 30 minutes: Rs 540

    sid = str(session.session_id)
    assert api.get("/api/me/dues").json()["total"] == 540.0
    order = api.post(f"/api/me/sessions/{sid}/pay").json()
    assert (order["amount"], order["amount_paise"], order["key_id"]) == (540.0, 54000, "rzp_test_unit")
    bad = api.post(f"/api/me/sessions/{sid}/pay/verify", json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_h", "razorpay_signature": "x"})
    assert (bad.status_code, bad.json()["error"]["code"]) == (400, "INVALID_SIGNATURE")
    ok = api.post(
        f"/api/me/sessions/{sid}/pay/verify",
        json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_h", "razorpay_signature": sign(order["order_id"], "pay_h")},
    )
    assert ok.status_code == 200 and ok.json()["bill_status"] == "PAID"
    assert api.get("/api/me/dues").json()["count"] == 0
    r = api.get(f"/api/me/sessions/{sid}/receipt").json()
    assert (r["bill_status"], r["total"], r["payment_reference"], r["energy_kwh"]) == ("PAID", 540.0, "pay_h", 27.0)
    assert api.post(f"/api/me/sessions/{sid}/pay").json()["error"]["code"] == "BILL_ALREADY_PAID"


def test_http_bill_endpoints_need_a_login(client):
    sid = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/api/me/sessions/{sid}/pay").status_code == 401
    assert client.post(f"/api/me/sessions/{sid}/pay/verify", json={}).status_code == 401
    assert client.get(f"/api/me/sessions/{sid}/receipt").status_code == 401
