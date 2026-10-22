"""Migration 014: walk-in settlement and the admin alerts table, called straight in SQL with a chosen time."""

from decimal import Decimal

import pytest

from database.tests.conftest import needs_db
from database.tests.test_jobs import (
    START, M, CCS, charger_status, make_booking, make_station, make_walk_in, one, start_session,
)

pytestmark = needs_db


def walk_in_session(db, charger, prepaid, minutes=120):
    """A paid walk-in that started at START: the booking, the payment, the session with its prepaid amount."""
    booking = make_walk_in(db, charger, START, minutes)
    db.execute(
        "INSERT INTO payments (booking_id, purpose, provider_order_id, provider_payment_id, amount, status) "
        "VALUES (%s, 'WALKIN_PREPAID', %s, %s, %s, 'CAPTURED')",
        (booking, f"plink_{booking}", f"pay_{booking}", prepaid),
    )
    session = start_session(db, booking, charger, START, source="WALK_IN")
    db.execute("UPDATE charging_sessions SET prepaid_amount = %s WHERE session_id = %s", (prepaid, session))
    return booking, session


def payment_of(db, booking):
    return db.execute("SELECT status, refunded_amount FROM payments WHERE booking_id = %s AND purpose = 'WALKIN_PREPAID'", (booking,)).fetchone()


def test_a_walk_in_that_stops_early_gets_the_rest_back(db):
    _, [charger] = make_station(db, CCS)
    booking, session = walk_in_session(db, charger, 200)
    one(db, "SELECT simulate_charger_event(%s, 'UNPLUG', %s)", charger, START + 6 * M)  # 5.4 kWh x 20 = 108
    bill, status, kwh = db.execute("SELECT bill_amount, bill_status, energy_kwh FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    assert (bill, status, kwh) == (Decimal("108.00"), "PREPAID_SETTLED", Decimal("5.400"))
    assert payment_of(db, booking) == ("PARTIALLY_REFUNDED", Decimal("92.00"))
    assert one(db, "SELECT refund_amount FROM bookings WHERE booking_id = %s", booking) == Decimal("92.00")


def test_the_bill_is_never_more_than_was_prepaid(db):
    _, [charger] = make_station(db, CCS)
    booking, session = walk_in_session(db, charger, 100)
    # The job runs once a minute, so by the time it looks the meter is past the money: 9 minutes = 8.1 kWh = Rs 162.
    one(db, "SELECT auto_stop_sessions(%s)", START + 9 * M)
    bill, kwh, reason = db.execute("SELECT bill_amount, energy_kwh, end_reason FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    assert (bill, kwh, reason) == (Decimal("100.00"), Decimal("5.000"), "PREPAID_USED")  # Rs 100 buys 5 kWh at Rs 20
    assert payment_of(db, booking) == ("CAPTURED", Decimal("0.00"))  # nothing left over


def test_using_none_of_it_refunds_everything(db):
    _, [charger] = make_station(db, CCS)
    booking, session = walk_in_session(db, charger, 200)
    one(db, "SELECT simulate_charger_event(%s, 'UNPLUG', %s)", charger, START)
    assert one(db, "SELECT bill_amount FROM charging_sessions WHERE session_id = %s", session) == Decimal("0.00")
    assert payment_of(db, booking) == ("REFUNDED", Decimal("200.00"))


def test_a_walk_in_stops_when_its_window_ends(db):
    _, [charger] = make_station(db, ("SLOW", "TYPE2", 7, 5))
    booking, session = walk_in_session(db, charger, 500, minutes=120)
    assert one(db, "SELECT auto_stop_sessions(%s)", START + 119 * M) == 0
    assert one(db, "SELECT auto_stop_sessions(%s)", START + 120 * M) == 1
    ended, reason, bill = db.execute("SELECT ended_at, end_reason, bill_amount FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    assert (ended, reason, bill) == (START + 120 * M, "SLOT_END_AUTO_STOP", Decimal("63.00"))  # 6.3 kW x 2 h x Rs 5
    assert payment_of(db, booking) == ("PARTIALLY_REFUNDED", Decimal("437.00"))
    assert charger_status(db, charger) == "AVAILABLE"


def test_app_sessions_are_billed_as_before(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START, 60, status="ACTIVE")
    session = start_session(db, booking, charger, START)
    one(db, "SELECT simulate_charger_event(%s, 'UNPLUG', %s)", charger, START + 30 * M)
    assert db.execute("SELECT bill_status, bill_amount FROM charging_sessions WHERE session_id = %s", (session,)).fetchone() == ("DUE", Decimal("540.00"))
    assert db.execute("SELECT count(*) FROM payments WHERE purpose = 'WALKIN_PREPAID'").fetchone()[0] == 0


def test_alert_kinds_are_checked(db):
    with pytest.raises(Exception, match="admin_alerts_kind_check"):
        db.execute("INSERT INTO admin_alerts (kind, message) VALUES ('MADE_UP', 'x')")
