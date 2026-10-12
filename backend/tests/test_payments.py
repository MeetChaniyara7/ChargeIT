"""Paying the booking fee: orders, signature checks, verify, webhooks, late payments (needs the test database).

Razorpay itself is replaced by a fake gateway, so nothing here touches the network or real keys.
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
from app.features.bookings import otp, service as bookings
from app.features.bookings.models import Booking
from app.features.payments import gateway, service
from app.features.payments.gateway import get_gateway, verify_payment_signature, verify_webhook_signature
from app.features.payments.schemas import VerifyRequest
from app.features.recommendations import service as recommendations
from app.main import app
from tests import factories
from tests.conftest import needs_db
from tests.factories import HOUR

KEY_SECRET = "test-razorpay-key-secret"
WEBHOOK_SECRET = "test-razorpay-webhook-secret"
NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
_numbers = itertools.count(1)


# ---------------------------------------------------------------- signatures (no database)

def sign(order_id, payment_id, secret=KEY_SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def test_a_genuine_payment_signature_passes_and_a_tampered_one_fails():
    good = sign("order_1", "pay_1")
    assert verify_payment_signature("order_1", "pay_1", good, KEY_SECRET)
    assert not verify_payment_signature("order_1", "pay_2", good, KEY_SECRET)        # different payment
    assert not verify_payment_signature("order_2", "pay_1", good, KEY_SECRET)        # different order
    assert not verify_payment_signature("order_1", "pay_1", good[:-1] + "0", KEY_SECRET)
    assert not verify_payment_signature("order_1", "pay_1", sign("order_1", "pay_1", "other-secret"), KEY_SECRET)
    assert not verify_payment_signature("order_1", "pay_1", "", KEY_SECRET)


def test_webhook_signatures_cover_the_exact_body():
    body = b'{"event":"payment.captured"}'
    good = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, good, WEBHOOK_SECRET)
    assert not verify_webhook_signature(body + b" ", good, WEBHOOK_SECRET)
    assert not verify_webhook_signature(body, "", WEBHOOK_SECRET)


def test_the_signature_matches_razorpays_own_method():
    """Our check agrees with the SDK's, so a real Checkout result will pass."""
    import razorpay

    client = razorpay.Client(auth=("rzp_test_unit", KEY_SECRET))
    params = {"razorpay_order_id": "order_9", "razorpay_payment_id": "pay_9", "razorpay_signature": sign("order_9", "pay_9")}
    assert client.utility.verify_payment_signature(params) is True  # the SDK raises on a bad signature
    assert verify_payment_signature("order_9", "pay_9", params["razorpay_signature"], KEY_SECRET)


# ---------------------------------------------------------------- with the database

pytestmark_db = needs_db


class FakeGateway:
    def __init__(self):
        self.orders = []

    def create_order(self, amount_paise, receipt, notes):
        order_id = f"order_fake_{next(_numbers)}"
        self.orders.append({"id": order_id, "amount": amount_paise, "receipt": receipt, "notes": notes})
        return order_id


class BrokenGateway:
    def create_order(self, amount_paise, receipt, notes):
        raise AppError(502, "PAYMENT_PROVIDER_ERROR", "The payment service is not responding. Please try again.")


def _committed(make):
    def wrapper(db, *args, **kwargs):
        result = make(db, *args, **kwargs)
        db.commit()
        return result

    return wrapper


make_booking = _committed(factories.make_booking)
make_charger = _committed(factories.make_charger)
make_station = _committed(factories.make_station)
make_user = _committed(factories.make_user)


def at(hour, minute=0):
    return datetime(2026, 10, 12, hour, minute, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    class Routes:
        def estimate(self, origin, destinations):
            from app.features.recommendations.osrm import Travel

            return [Travel(5.0, 2.0, True) for _ in destinations]

    monkeypatch.setattr(recommendations, "travel_times", Routes())


@pytest.fixture
def world(db):
    station = make_station(db, "Pay hub", 23.03, 72.55)
    return {"station": station, "a": make_charger(db, station, "CCS2", 60, 20, label="A"), "user": make_user(db), "other": make_user(db)}


@pytest.fixture
def fake():
    return FakeGateway()


def held(db, world, start=None, now=NOW, user="user"):
    return bookings.create_hold(db, world[user], world["a"], start or at(12), 2, None, now)


def order_for(db, world, booking, fake, now=NOW, user="user"):
    return service.create_order(db, world[user], booking.booking_id, fake, now)


def verify(db, world, order_id, payment_id="pay_ok", now=NOW, user="user", signature=None):
    return service.verify(
        db, world[user],
        VerifyRequest(razorpay_order_id=order_id, razorpay_payment_id=payment_id, razorpay_signature=signature or sign(order_id, payment_id)),
        now,
    )


def status_of(db, booking_id):
    return db.execute(text("SELECT status FROM bookings WHERE booking_id = :b"), {"b": booking_id}).scalar_one()


def payment_row(db, order_id):
    return db.execute(text("SELECT status, amount, refunded_amount, provider_payment_id, booking_id FROM payments WHERE provider_order_id = :o"), {"o": order_id}).one()


# ---- orders

@needs_db
def test_the_order_is_for_199_rupees_in_paise_and_ties_back_to_the_booking(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    assert order.amount == 199 and order.amount_paise == 19900 and order.currency == "INR" and order.key_id == "rzp_test_unit"
    assert fake.orders == [{"id": order.order_id, "amount": 19900, "receipt": str(booking.booking_id),
                            "notes": {"purpose": "BOOKING_FEE", "booking_id": str(booking.booking_id)}}]
    assert tuple(payment_row(db, order.order_id))[:3] == ("CREATED", 199, 0)
    assert "secret" not in order.model_dump_json().lower()


@needs_db
def test_checkout_closes_a_little_before_the_hold_runs_out(db, world, fake):
    booking = held(db, world)  # hold lasts 300 s
    assert order_for(db, world, booking, fake, now=NOW).checkout_timeout_seconds == 285
    assert order_for(db, world, booking, fake, now=NOW + timedelta(seconds=280)).checkout_timeout_seconds == 20
    assert order_for(db, world, booking, fake, now=NOW + timedelta(seconds=295)).checkout_timeout_seconds <= 5


@needs_db
def test_asking_for_the_order_again_returns_the_same_order(db, world, fake):
    booking = held(db, world)
    first, second = order_for(db, world, booking, fake), order_for(db, world, booking, fake)
    assert first.order_id == second.order_id and len(fake.orders) == 1


@needs_db
def test_no_order_for_an_expired_or_foreign_or_confirmed_booking(db, world, fake):
    booking = held(db, world)
    with pytest.raises(AppError) as error:
        order_for(db, world, booking, fake, now=NOW + timedelta(minutes=6))
    assert error.value.code == "HOLD_EXPIRED"
    assert status_of(db, booking.booking_id) == "EXPIRED"

    mine = held(db, world, at(14))
    with pytest.raises(AppError) as error:
        order_for(db, world, mine, fake, user="other")
    assert error.value.status_code == 404

    instant = bookings.create_instant(db, world["other"], world["a"], None, NOW + timedelta(hours=5))
    with pytest.raises(AppError) as error:
        service.create_order(db, world["other"], instant.booking_id, fake, NOW + timedelta(hours=5))
    assert error.value.code == "BOOKING_NOT_PAYABLE"


@needs_db
def test_a_payment_service_outage_keeps_the_hold_and_says_so(db, world):
    booking = held(db, world)
    with pytest.raises(AppError) as error:
        service.create_order(db, world["user"], booking.booking_id, BrokenGateway(), NOW)
    assert error.value.status_code == 502 and error.value.code == "PAYMENT_PROVIDER_ERROR"
    assert status_of(db, booking.booking_id) == "HELD"
    assert db.scalar(text("SELECT count(*) FROM payments WHERE booking_id = :b"), {"b": booking.booking_id}) == 0


# ---- verify

@needs_db
def test_a_verified_payment_confirms_the_booking_and_shows_the_code_once(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    result = verify(db, world, order.order_id, "pay_1", now=NOW + timedelta(minutes=1))
    assert result.outcome == "CONFIRMED" and result.booking.status == "CONFIRMED" and result.booking.fee_paid
    assert result.otp and len(result.otp) == 6
    stored = db.get(Booking, booking.booking_id)
    assert otp.matches(result.otp, stored.otp_hash) and result.otp not in stored.otp_hash
    assert tuple(payment_row(db, order.order_id))[:4] == ("CAPTURED", 199, 0, "pay_1")
    actor = db.execute(text("SELECT actor FROM booking_events WHERE booking_id = :b AND to_status = 'CONFIRMED'"), {"b": booking.booking_id}).scalar_one()
    assert actor == "USER"
    # The code is never shown again by the booking itself.
    assert result.otp not in bookings.get_booking(db, world["user"], booking.booking_id, NOW).model_dump_json()


@needs_db
def test_a_tampered_signature_changes_nothing(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    for signature in (sign(order.order_id, "pay_other"), sign(order.order_id, "pay_1", "wrong-secret"), "00" * 32):
        with pytest.raises(AppError) as error:
            verify(db, world, order.order_id, "pay_1", signature=signature)
        assert error.value.status_code == 400 and error.value.code == "INVALID_SIGNATURE"
    assert status_of(db, booking.booking_id) == "HELD" and payment_row(db, order.order_id).status == "CREATED"


@needs_db
def test_verifying_twice_does_not_issue_a_second_code(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    first = verify(db, world, order.order_id, "pay_1")
    stored = db.get(Booking, booking.booking_id).otp_hash
    again = verify(db, world, order.order_id, "pay_1")
    assert first.otp and again.outcome == "ALREADY_CONFIRMED" and again.otp is None
    assert db.get(Booking, booking.booking_id).otp_hash == stored


@needs_db
def test_someone_elses_order_or_an_unknown_order_is_not_found(db, world, fake):
    order = order_for(db, world, held(db, world), fake)
    with pytest.raises(AppError) as error:
        verify(db, world, order.order_id, user="other")
    assert error.value.status_code == 404
    with pytest.raises(AppError) as error:
        verify(db, world, "order_unknown")
    assert error.value.status_code == 404


@needs_db
def test_paying_in_the_last_second_still_counts(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    result = verify(db, world, order.order_id, now=NOW + timedelta(minutes=5, seconds=3))  # hold ran out, nobody took the slot
    assert result.outcome == "CONFIRMED" and result.otp


# ---- late payments

@needs_db
def test_a_late_payment_rebooks_the_same_slot_when_it_is_still_free(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    bookings.expire_if_stale(db, db.get(Booking, booking.booking_id), NOW + timedelta(minutes=6))  # someone looked: it expired
    assert status_of(db, booking.booking_id) == "EXPIRED"

    result = verify(db, world, order.order_id, now=NOW + timedelta(minutes=7))
    assert result.outcome == "CONFIRMED" and result.otp
    assert result.booking.booking_id != booking.booking_id and result.booking.status == "CONFIRMED"
    assert (result.booking.start, result.booking.end) == (at(12), at(13))
    assert payment_row(db, order.order_id).booking_id == result.booking.booking_id


@needs_db
def test_a_late_payment_is_refunded_in_full_when_the_slot_was_taken(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    later = NOW + timedelta(minutes=7)
    bookings.create_hold(db, world["other"], world["a"], at(12), 2, None, later)  # takes the slot (expiring the first hold)
    assert status_of(db, booking.booking_id) == "EXPIRED"

    result = verify(db, world, order.order_id, now=later)
    assert result.outcome == "REFUNDED_LATE" and result.otp is None and result.refund_amount == 199
    assert "refund" in result.message.lower()
    row = payment_row(db, order.order_id)
    assert (row.status, row.refunded_amount, row.booking_id) == ("REFUNDED", 199, booking.booking_id)
    assert status_of(db, booking.booking_id) == "EXPIRED"


@needs_db
def test_paying_for_a_cancelled_booking_is_refunded(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    bookings.cancel(db, world["user"], booking.booking_id, NOW + timedelta(minutes=1))
    result = verify(db, world, order.order_id, now=NOW + timedelta(minutes=2))
    assert result.outcome == "REFUNDED_LATE" and result.refund_amount == 199


@needs_db
def test_a_payment_after_the_slot_is_over_is_refunded(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    result = verify(db, world, order.order_id, now=at(12, 30))  # the 12:00 slot started half an hour ago
    assert result.outcome == "REFUNDED_LATE"
    assert status_of(db, booking.booking_id) == "EXPIRED"


# ---- webhooks

def webhook_body(order_id, payment_id, event="payment.captured"):
    return json.dumps({"event": event, "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id, "status": "captured"}}}}).encode()


def deliver(db, body, event_id="evt_1", secret=WEBHOOK_SECRET, now=NOW):
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return service.handle_webhook(db, body, signature, event_id, now)


@needs_db
def test_a_webhook_confirms_the_booking_when_the_browser_never_reported(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    assert deliver(db, webhook_body(order.order_id, "pay_w1")) == "processed"
    assert status_of(db, booking.booking_id) == "CONFIRMED"
    assert tuple(payment_row(db, order.order_id))[:4] == ("CAPTURED", 199, 0, "pay_w1")
    actor = db.execute(text("SELECT actor FROM booking_events WHERE booking_id = :b AND to_status = 'CONFIRMED'"), {"b": booking.booking_id}).scalar_one()
    assert actor == "SYSTEM"
    # The driver was not on the page, so the code was not shown: they ask for a new one.
    assert bookings.show_new_code(db, world["user"], booking.booking_id, NOW).otp


@needs_db
def test_the_same_webhook_event_is_processed_once(db, world, fake):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    body = webhook_body(order.order_id, "pay_w1")
    assert deliver(db, body, "evt_same") == "processed"
    stored = db.get(Booking, booking.booking_id).otp_hash
    assert deliver(db, body, "evt_same") == "duplicate"
    assert db.scalar(text("SELECT count(*) FROM webhook_events WHERE provider_event_id = 'evt_same'")) == 1
    assert db.get(Booking, booking.booking_id).otp_hash == stored
    assert db.execute(text("SELECT processed_at FROM webhook_events WHERE provider_event_id = 'evt_same'")).scalar_one() is not None


@needs_db
def test_webhook_after_verify_and_verify_after_webhook_change_nothing_more(db, world, fake):
    first = held(db, world)
    order = order_for(db, world, first, fake)
    verified = verify(db, world, order.order_id, "pay_1")
    stored = db.get(Booking, first.booking_id).otp_hash
    assert deliver(db, webhook_body(order.order_id, "pay_1"), "evt_a") == "processed"  # recorded, but nothing left to do
    assert db.get(Booking, first.booking_id).otp_hash == stored and verified.otp

    second = held(db, world, at(15), user="other")
    order2 = order_for(db, world, second, fake, user="other")
    deliver(db, webhook_body(order2.order_id, "pay_2"), "evt_b")
    again = verify(db, world, order2.order_id, "pay_2", user="other")
    assert again.outcome == "ALREADY_CONFIRMED" and again.otp is None


@needs_db
def test_webhooks_with_a_bad_signature_or_body_are_refused(db, world, fake):
    order = order_for(db, world, held(db, world), fake)
    body = webhook_body(order.order_id, "pay_x")
    with pytest.raises(AppError) as error:
        deliver(db, body, secret="wrong-secret")
    assert error.value.status_code == 400 and error.value.code == "INVALID_SIGNATURE"
    assert db.scalar(text("SELECT count(*) FROM webhook_events")) == 0
    assert payment_row(db, order.order_id).status == "CREATED"
    for bad in (b"not json", b"[1, 2]"):
        with pytest.raises(AppError) as error:
            deliver(db, bad)
        assert error.value.code == "INVALID_PAYLOAD"


@needs_db
def test_other_events_and_unknown_orders_are_acknowledged_and_ignored(db, world, fake):
    order = order_for(db, world, held(db, world), fake)
    assert deliver(db, webhook_body(order.order_id, "pay_f", "payment.failed"), "evt_f") == "ignored"
    assert payment_row(db, order.order_id).status == "CREATED"
    assert deliver(db, webhook_body("order_not_ours", "pay_z"), "evt_z") == "ignored"


@needs_db
def test_a_webhook_without_an_event_id_is_still_deduplicated(db, world, fake):
    order = order_for(db, world, held(db, world), fake)
    body = webhook_body(order.order_id, "pay_w")
    assert deliver(db, body, event_id=None) == "processed"
    assert deliver(db, body, event_id=None) == "duplicate"


# ---- over HTTP

@pytest.fixture
def api(db_client, world, fake):
    app.dependency_overrides[get_gateway] = lambda: fake
    app.dependency_overrides[get_current_user] = lambda: User(user_id=world["user"], email="driver@test.dev", role="USER")
    return db_client


@needs_db
def test_http_book_pay_and_get_the_code(api, world):
    from app.core.slots import ceil_to_slot

    start = (ceil_to_slot(datetime.now(timezone.utc)) + timedelta(hours=3)).isoformat()
    booking = api.post("/api/bookings", json={"charger_id": str(world["a"]), "start": start, "blocks": 2}).json()
    order = api.post("/api/payments/orders", json={"booking_id": booking["booking_id"]}).json()
    assert order["amount"] == 199 and order["key_id"] == "rzp_test_unit"

    verified = api.post(
        "/api/payments/verify",
        json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_http", "razorpay_signature": sign(order["order_id"], "pay_http")},
    )
    assert verified.status_code == 200
    body = verified.json()
    assert body["outcome"] == "CONFIRMED" and len(body["otp"]) == 6 and body["booking"]["status"] == "CONFIRMED"
    assert api.get(f"/api/bookings/{booking['booking_id']}").json()["fee_paid"] is True

    bad = api.post("/api/payments/verify", json={"razorpay_order_id": "o", "razorpay_payment_id": "p", "razorpay_signature": "s"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_SIGNATURE"


@needs_db
def test_http_webhook_checks_the_signature_on_the_raw_body(api, world, fake, db):
    booking = held(db, world)
    order = order_for(db, world, booking, fake)
    body = webhook_body(order.order_id, "pay_hook")
    good = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Razorpay-Signature": good, "X-Razorpay-Event-Id": "evt_http", "Content-Type": "application/json"}
    assert api.post("/api/payments/webhook", content=body, headers=headers).json() == {"status": "processed"}
    assert api.post("/api/payments/webhook", content=body, headers=headers).json() == {"status": "duplicate"}
    forged = api.post("/api/payments/webhook", content=body, headers={**headers, "X-Razorpay-Signature": "00", "X-Razorpay-Event-Id": "evt_other"})
    assert forged.status_code == 400 and forged.json()["error"]["code"] == "INVALID_SIGNATURE"
    assert api.post("/api/payments/webhook", content=body).status_code == 400  # no signature at all


def test_payment_endpoints_that_need_a_login(client):
    assert client.post("/api/payments/orders", json={"booking_id": "00000000-0000-0000-0000-000000000000"}).status_code == 401
    assert client.post("/api/payments/verify", json={}).status_code == 401


def test_missing_secrets_give_a_clear_503_not_a_crash(monkeypatch):
    from app.config import require_setting

    monkeypatch.setattr("app.config.get_settings", lambda: type("S", (), {"razorpay_key_secret": None})())
    with pytest.raises(AppError) as error:
        require_setting("razorpay_key_secret")
    assert error.value.status_code == 503 and error.value.code == "SETTING_MISSING" and "RAZORPAY_KEY_SECRET" in error.value.message


def test_the_real_gateway_turns_provider_failures_into_a_502(monkeypatch):
    import razorpay

    class Boom:
        def __init__(self, auth):
            pass

        order = type("O", (), {"create": staticmethod(lambda data: (_ for _ in ()).throw(RuntimeError("down")))})()

    monkeypatch.setattr(razorpay, "Client", Boom)
    with pytest.raises(AppError) as error:
        gateway.RazorpayGateway().create_order(19900, "r1", {})
    assert error.value.status_code == 502


def test_the_real_gateway_sends_the_amount_in_paise(monkeypatch):
    import razorpay

    sent = {}

    class Client:
        def __init__(self, auth):
            sent["auth"] = auth

        class order:
            @staticmethod
            def create(data):
                sent["data"] = data
                return {"id": "order_real"}

    monkeypatch.setattr(razorpay, "Client", Client)
    assert gateway.RazorpayGateway().create_order(19900, "booking-1", {"purpose": "BOOKING_FEE"}) == "order_real"
    assert sent["auth"] == ("rzp_test_unit", KEY_SECRET)
    assert sent["data"]["amount"] == 19900 and sent["data"]["currency"] == "INR" and sent["data"]["receipt"] == "booking-1"
