"""The background jobs (migration 011), called directly with a chosen `p_now`.

Each test builds a tiny world (one station, one or two chargers) and then pretends it is any
moment it likes, so nothing waits for a real clock.
"""

import itertools
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from database.tests.conftest import needs_db

pytestmark = needs_db

START = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)  # a slot starting at 10:00 UTC (15:30 IST)
M = timedelta(minutes=1)
_n = itertools.count(1)


# ---------------------------------------------------------------- helpers

def one(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def make_station(conn, *chargers, name="Job hub"):
    """A station with chargers given as (label, connector, power_kw, price). Returns (station_id, [charger_ids])."""
    station = one(conn, "INSERT INTO stations (name, latitude, longitude, data_source) VALUES (%s, 23.03, 72.55, 'manual') RETURNING station_id", f"{name} {next(_n)}")
    ids = [
        one(conn, "INSERT INTO chargers (station_id, label, connector_type, current_type, power_kw, price_per_kwh, data_source) "
                  "VALUES (%s, %s, %s, 'DC', %s, %s, 'manual') RETURNING charger_id", station, label, connector, power, price)
        for label, connector, power, price in chargers
    ]
    return station, ids


def make_user(conn):
    return one(conn, "INSERT INTO users (email) VALUES (%s) RETURNING user_id", f"job{next(_n)}@test.dev")


def make_vehicle(conn, user, battery=100):
    return one(conn, "INSERT INTO vehicles (user_id, nickname, connector_type, battery_kwh) VALUES (%s, 'Car', 'CCS2', %s) RETURNING vehicle_id", user, battery)


def make_booking(conn, charger, start, minutes=60, *, status="CONFIRMED", fee=199, user=None, vehicle=None, hold_until=None, paid=True):
    """An app booking taken through its legal steps: HELD, then CONFIRMED, then ACTIVE if asked."""
    user = user or make_user(conn)
    end = start + minutes * M
    booking = one(
        conn,
        "INSERT INTO bookings (user_id, charger_id, vehicle_id, source, status, time_range, hold_expires_at, booking_fee) "
        "VALUES (%s, %s, %s, 'APP', 'HELD', tstzrange(%s, %s, '[)'), %s, %s) RETURNING booking_id",
        user, charger, vehicle, start, end, hold_until or start, fee,
    )
    if status in ("CONFIRMED", "ACTIVE"):
        conn.execute("UPDATE bookings SET status = 'CONFIRMED', hold_expires_at = NULL, otp_hash = 'hash' WHERE booking_id = %s", (booking,))
        if paid and fee:
            conn.execute(
                "INSERT INTO payments (booking_id, purpose, provider_order_id, provider_payment_id, amount, status) "
                "VALUES (%s, 'BOOKING_FEE', %s, %s, %s, 'CAPTURED')", (booking, f"order_{next(_n)}", f"pay_{next(_n)}", fee),
            )
    if status == "ACTIVE":
        conn.execute("UPDATE bookings SET status = 'ACTIVE', otp_used_at = %s WHERE booking_id = %s", (start, booking))
    return booking


def make_walk_in(conn, charger, start, minutes=60):
    """A kiosk walk-in: no account, HELD while the QR is on screen, ACTIVE once paid (a legal move for WALK_IN)."""
    booking = one(
        conn,
        "INSERT INTO bookings (charger_id, source, status, time_range, hold_expires_at) "
        "VALUES (%s, 'WALK_IN', 'HELD', tstzrange(%s, %s, '[)'), %s) RETURNING booking_id",
        charger, start, start + minutes * M, start + 3 * M,
    )
    conn.execute("UPDATE bookings SET status = 'ACTIVE', hold_expires_at = NULL WHERE booking_id = %s", (booking,))
    return booking


def start_session(conn, booking, charger, at, source="BOOKING", soc=None):
    conn.execute("SELECT apply_charger_event(%s, 'SESSION_START', '{}', 'SYSTEM', %s)", (charger, at))
    return one(conn, "INSERT INTO charging_sessions (booking_id, charger_id, source, started_at, start_soc_percent) "
                     "VALUES (%s, %s, %s, %s, %s) RETURNING session_id", booking, charger, source, at, soc)


def status_of(conn, booking):
    return one(conn, "SELECT status FROM bookings WHERE booking_id = %s", booking)


def charger_status(conn, charger):
    return one(conn, "SELECT status FROM chargers WHERE charger_id = %s", charger)


def events(conn, booking):
    return conn.execute("SELECT from_status, to_status, actor, reason FROM booking_events WHERE booking_id = %s ORDER BY event_id", (booking,)).fetchall()


CCS = ("CCS2-1", "CCS2", 60, 20)


# ---------------------------------------------------------------- expire_holds

def test_a_hold_expires_at_exactly_five_minutes_and_not_before(db):
    _, [charger] = make_station(db, CCS)
    deadline = START + 5 * M
    booking = make_booking(db, charger, START + 60 * M, status="HELD", hold_until=deadline, paid=False)

    assert one(db, "SELECT expire_holds(%s)", deadline - timedelta(seconds=1)) == 0
    assert status_of(db, booking) == "HELD"
    assert one(db, "SELECT expire_holds(%s)", deadline) == 1
    assert status_of(db, booking) == "EXPIRED"
    assert events(db, booking)[-1] == ("HELD", "EXPIRED", "SYSTEM", "Hold ran out")
    assert one(db, "SELECT expire_holds(%s)", deadline + 99 * M) == 0  # nothing left to do


def test_an_expired_hold_frees_the_slot(db):
    _, [charger] = make_station(db, CCS)
    make_booking(db, charger, START, status="HELD", hold_until=START - 10 * M, paid=False)
    one(db, "SELECT expire_holds(%s)", START - 5 * M)
    assert make_booking(db, charger, START)  # the exclusion constraint no longer blocks it


def test_a_confirmed_booking_is_never_expired(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START)
    one(db, "SELECT expire_holds(%s)", START + 999 * M)
    assert status_of(db, booking) == "CONFIRMED"


# ---------------------------------------------------------------- reservation locks and outside starts

def test_the_charger_is_reserved_15_minutes_before_the_start(db):
    _, [charger] = make_station(db, CCS)
    make_booking(db, charger, START)
    assert one(db, "SELECT apply_reservation_locks(%s)", START - 16 * M) == 0
    assert charger_status(db, charger) == "AVAILABLE"
    assert one(db, "SELECT apply_reservation_locks(%s)", START - 15 * M) == 1
    assert charger_status(db, charger) == "RESERVED"
    assert one(db, "SELECT event FROM charger_events WHERE charger_id = %s ORDER BY event_id DESC LIMIT 1", charger) == "RESERVE"


def test_an_outside_start_is_refused_during_the_lock_but_accepted_before_it(db):
    _, [charger] = make_station(db, CCS)
    make_booking(db, charger, START)

    refused = one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START - 14 * M)
    assert refused["accepted"] is False and "reserved" in refused["reason"]
    assert charger_status(db, charger) == "AVAILABLE"  # refused, so nothing changed (and the job has not even run yet)
    assert one(db, "SELECT count(*) FROM charging_sessions WHERE charger_id = %s", charger) == 0
    assert one(db, "SELECT event FROM charger_events WHERE charger_id = %s ORDER BY event_id DESC LIMIT 1", charger) == "REJECTED_EXTERNAL_START"

    one(db, "SELECT apply_reservation_locks(%s)", START - 14 * M)
    refused_again = one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START - 13 * M)
    assert refused_again["accepted"] is False and charger_status(db, charger) == "RESERVED"

    _, [other] = make_station(db, CCS)
    make_booking(db, other, START)
    accepted = one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", other, START - 16 * M)  # 16 minutes ahead: before the lock
    assert accepted["accepted"] is True and charger_status(db, other) == "CHARGING"
    assert one(db, "SELECT source FROM charging_sessions WHERE charger_id = %s AND ended_at IS NULL", other) == "EXTERNAL"


def test_the_reservation_is_released_when_the_booking_goes_away(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START)
    one(db, "SELECT apply_reservation_locks(%s)", START - 10 * M)
    assert charger_status(db, charger) == "RESERVED"
    one(db, "SELECT mark_no_shows(%s)", START + 10 * M)
    assert status_of(db, booking) == "NO_SHOW"
    one(db, "SELECT apply_reservation_locks(%s)", START + 11 * M)
    assert charger_status(db, charger) == "AVAILABLE"
    assert one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START + 12 * M)["accepted"] is True  # free for outsiders again


def test_a_driver_is_warned_when_an_outside_session_is_still_running_at_lock_time(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START)
    one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START - 30 * M)
    one(db, "SELECT apply_reservation_locks(%s)", START - 15 * M)
    assert charger_status(db, charger) == "CHARGING"  # cannot be reserved while in use
    kind, text = db.execute("SELECT notice_kind, notice_text FROM bookings WHERE booking_id = %s", (booking,)).fetchone()
    assert kind == "WARNING" and "still charging" in text

    one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_STOP', %s)", charger, START - 5 * M)
    one(db, "SELECT apply_reservation_locks(%s)", START - 4 * M)
    assert db.execute("SELECT notice_kind FROM bookings WHERE booking_id = %s", (booking,)).fetchone()[0] is None
    assert charger_status(db, charger) == "RESERVED"  # stopping returns it to its reservation straight away


# ---------------------------------------------------------------- no-shows

def test_no_show_at_ten_minutes_after_the_start_with_the_fee_kept_and_the_slot_freed(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START)
    assert one(db, "SELECT mark_no_shows(%s)", START + 10 * M - timedelta(seconds=1)) == 0
    assert status_of(db, booking) == "CONFIRMED"
    assert one(db, "SELECT mark_no_shows(%s)", START + 10 * M) == 1
    assert status_of(db, booking) == "NO_SHOW"
    assert events(db, booking)[-1][1:3] == ("NO_SHOW", "SYSTEM")
    assert db.execute("SELECT status, refunded_amount FROM payments WHERE booking_id = %s", (booking,)).fetchone() == ("CAPTURED", Decimal("0.00"))  # fee kept
    assert db.execute("SELECT booking_fee, refund_amount FROM bookings WHERE booking_id = %s", (booking,)).fetchone() == (Decimal("199.00"), Decimal("0.00"))
    assert make_booking(db, charger, START + 15 * M, 30)  # the rest of that window is free again


def test_a_booking_whose_code_was_used_is_not_a_no_show(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START, status="ACTIVE")
    assert one(db, "SELECT mark_no_shows(%s)", START + 30 * M) == 0
    assert status_of(db, booking) == "ACTIVE"


# ---------------------------------------------------------------- occupied at the start time

def occupy(db, charger, at=START - 30 * M):
    assert one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, at)["accepted"] is True


def test_occupied_at_the_start_moves_the_booking_to_another_free_charger(db):
    _, [a, b] = make_station(db, ("CCS2-1", "CCS2", 60, 20), ("CCS2-2", "CCS2", 60, 20))
    booking = make_booking(db, a, START)
    occupy(db, a)
    assert one(db, "SELECT resolve_occupied_starts(%s)", START - 1 * M) == 0  # the start time has not come yet
    assert one(db, "SELECT resolve_occupied_starts(%s)", START) == 1
    charger, moved_from, kind, text, status = db.execute(
        "SELECT charger_id, moved_from_charger_id, notice_kind, notice_text, status FROM bookings WHERE booking_id = %s", (booking,)
    ).fetchone()
    assert (charger, moved_from, kind, status) == (b, a, "MOVED", "CONFIRMED")
    assert text == "Moved from CCS2-1 to CCS2-2, same time."
    assert events(db, booking)[-1] == ("CONFIRMED", "CONFIRMED", "SYSTEM", "Charger CCS2-1 was occupied at the start time; moved to CCS2-2")
    assert one(db, "SELECT resolve_occupied_starts(%s)", START + M) == 0  # already resolved


def test_the_closest_power_is_chosen_when_several_chargers_are_free(db):
    _, [a, slow, close] = make_station(db, ("A", "CCS2", 60, 20), ("B", "CCS2", 7, 10), ("C", "CCS2", 50, 18))
    booking = make_booking(db, a, START)
    occupy(db, a)
    one(db, "SELECT resolve_occupied_starts(%s)", START)
    assert one(db, "SELECT charger_id FROM bookings WHERE booking_id = %s", booking) == close


def test_no_charger_free_cancels_with_a_full_refund(db):
    _, [a, b, c] = make_station(db, ("CCS2-1", "CCS2", 60, 20), ("CCS2-2", "CCS2", 60, 20), ("T2-1", "TYPE2", 22, 10))
    booking = make_booking(db, a, START)
    make_booking(db, b, START + 15 * M, 30)   # the other CCS2 charger is booked during this booking
    occupy(db, a)                              # (a Type 2 charger does not fit a CCS2 car)
    assert one(db, "SELECT resolve_occupied_starts(%s)", START) == 1
    row = db.execute("SELECT status, refund_amount, notice_kind, cancelled_at FROM bookings WHERE booking_id = %s", (booking,)).fetchone()
    assert row[0] == "CANCELLED" and row[1] == Decimal("199.00") and row[2] == "CANCELLED_NO_CHARGER" and row[3] == START
    assert db.execute("SELECT status, refunded_amount FROM payments WHERE booking_id = %s", (booking,)).fetchone() == ("REFUNDED", Decimal("199.00"))
    assert events(db, booking)[-1][1:3] == ("CANCELLED", "SYSTEM")


def test_a_broken_charger_at_the_start_is_handled_the_same_way(db):
    _, [a, b] = make_station(db, ("CCS2-1", "CCS2", 60, 20), ("CCS2-2", "CCS2", 60, 20))
    booking = make_booking(db, a, START)
    one(db, "SELECT simulate_charger_event(%s, 'FAULT', %s)", a, START - 5 * M)
    one(db, "SELECT resolve_occupied_starts(%s)", START)
    assert one(db, "SELECT charger_id FROM bookings WHERE booking_id = %s", booking) == b


def test_a_free_charger_with_an_unexpired_hold_in_that_time_is_not_used(db):
    _, [a, b] = make_station(db, ("CCS2-1", "CCS2", 60, 20), ("CCS2-2", "CCS2", 60, 20))
    booking = make_booking(db, a, START)
    make_booking(db, b, START, status="HELD", hold_until=START + 3 * M, paid=False)  # someone is paying for it
    occupy(db, a)
    one(db, "SELECT resolve_occupied_starts(%s)", START)
    assert status_of(db, booking) == "CANCELLED"


def test_a_booking_that_is_not_in_trouble_is_left_alone(db):
    _, [a, b] = make_station(db, ("CCS2-1", "CCS2", 60, 20), ("CCS2-2", "CCS2", 60, 20))
    booking = make_booking(db, a, START)
    occupy(db, b)  # the OTHER charger is busy
    assert one(db, "SELECT resolve_occupied_starts(%s)", START) == 0
    assert one(db, "SELECT charger_id FROM bookings WHERE booking_id = %s", booking) == a


# ---------------------------------------------------------------- sessions and bills

def test_a_session_stops_at_the_slot_end_with_the_right_bill(db):
    _, [charger] = make_station(db, CCS)
    user = make_user(db)
    booking = make_booking(db, charger, START, 60, status="ACTIVE", user=user, vehicle=make_vehicle(db, user, 100))
    session = start_session(db, booking, charger, START)

    assert one(db, "SELECT auto_stop_sessions(%s)", START + 59 * M) == 0
    assert one(db, "SELECT ended_at FROM charging_sessions WHERE session_id = %s", session) is None

    assert one(db, "SELECT auto_stop_sessions(%s)", START + 60 * M) == 1
    ended, reason, kwh, bill, bill_status = db.execute(
        "SELECT ended_at, end_reason, energy_kwh, bill_amount, bill_status FROM charging_sessions WHERE session_id = %s", (session,)
    ).fetchone()
    # 60 kW x 1 hour x 0.9 = 54 kWh; at ₹20 a kWh = ₹1,080
    assert (ended, reason, kwh, bill, bill_status) == (START + 60 * M, "SLOT_END_AUTO_STOP", Decimal("54.000"), Decimal("1080.00"), "DUE")
    assert status_of(db, booking) == "COMPLETED" and events(db, booking)[-1][1:3] == ("COMPLETED", "SYSTEM")
    assert charger_status(db, charger) == "AVAILABLE"


def test_a_late_job_still_bills_only_up_to_the_slot_end(db):
    _, [charger] = make_station(db, CCS)
    user = make_user(db)
    booking = make_booking(db, charger, START, 30, status="ACTIVE", user=user, vehicle=make_vehicle(db, user, 100))
    session = start_session(db, booking, charger, START)
    one(db, "SELECT auto_stop_sessions(%s)", START + 45 * M)  # the job ran 15 minutes late
    ended, kwh = db.execute("SELECT ended_at, energy_kwh FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    assert ended == START + 30 * M and kwh == Decimal("27.000")


def test_the_battery_limits_the_energy(db):
    _, [charger] = make_station(db, CCS)
    user = make_user(db)
    booking = make_booking(db, charger, START, 120, status="ACTIVE", user=user, vehicle=make_vehicle(db, user, 30))
    session = start_session(db, booking, charger, START)  # starts at the default 20%: room for 24 kWh
    one(db, "SELECT auto_stop_sessions(%s)", START + 120 * M)
    kwh, bill = db.execute("SELECT energy_kwh, bill_amount FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    assert (kwh, bill) == (Decimal("24.000"), Decimal("480.00"))


def test_a_session_with_no_vehicle_uses_the_default_battery_and_a_known_start_charge_is_respected(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START, 120, status="ACTIVE")
    session = start_session(db, booking, charger, START, soc=70)  # 40 kWh default battery x 30% = 12 kWh of room
    one(db, "SELECT auto_stop_sessions(%s)", START + 120 * M)
    assert one(db, "SELECT energy_kwh FROM charging_sessions WHERE session_id = %s", session) == Decimal("12.000")


def test_a_free_charger_gives_a_bill_of_zero_that_counts_as_paid(db):
    _, [charger] = make_station(db, ("FREE", "CCS2", 22, 0))
    booking = make_booking(db, charger, START, 60, status="ACTIVE")
    session = start_session(db, booking, charger, START)
    one(db, "SELECT auto_stop_sessions(%s)", START + 60 * M)
    bill, status, paid_at = db.execute("SELECT bill_amount, bill_status, paid_at FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    assert (bill, status) == (Decimal("0.00"), "PAID") and paid_at is not None


def test_finishing_twice_changes_nothing(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START, 60, status="ACTIVE")
    session = start_session(db, booking, charger, START)
    one(db, "SELECT finish_session(%s, %s, 'USER_STOP', 'USER', %s)", session, START + 30 * M, START + 30 * M)
    first = db.execute("SELECT ended_at, energy_kwh, bill_amount FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    one(db, "SELECT finish_session(%s, %s, 'SLOT_END_AUTO_STOP', 'SYSTEM', %s)", session, START + 60 * M, START + 60 * M)
    assert db.execute("SELECT ended_at, energy_kwh, bill_amount FROM charging_sessions WHERE session_id = %s", (session,)).fetchone() == first
    assert one(db, "SELECT end_reason FROM charging_sessions WHERE session_id = %s", session) == "USER_STOP"


def test_outside_sessions_are_never_stopped_or_billed_by_the_job(db):
    _, [charger] = make_station(db, CCS)
    one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START)
    assert one(db, "SELECT auto_stop_sessions(%s)", START + 600 * M) == 0
    one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_STOP', %s)", charger, START + 90 * M)
    bill, status, kwh = db.execute("SELECT bill_amount, bill_status, energy_kwh FROM charging_sessions WHERE charger_id = %s", (charger,)).fetchone()
    assert bill is None and status is None            # not ours to bill
    assert kwh == Decimal("32.000")                   # 81 kWh of charging, but the default 40 kWh battery only had room for 32
    assert charger_status(db, charger) == "AVAILABLE"


def test_walk_in_sessions_stop_before_the_next_booking_and_when_the_prepaid_amount_is_used(db):
    _, [a, b] = make_station(db, ("A", "CCS2", 60, 20), ("B", "CCS2", 60, 20))
    make_booking(db, a, START + 70 * M)
    early = start_session(db, make_walk_in(db, a, START, 65), a, START, source="WALK_IN")  # a real walk-in window ends 5 minutes before the next booking
    assert one(db, "SELECT auto_stop_sessions(%s)", START + 64 * M) == 0
    assert one(db, "SELECT auto_stop_sessions(%s)", START + 65 * M) == 1  # five minutes before the next booking at +70
    ended, reason, status = db.execute("SELECT ended_at, end_reason, bill_status FROM charging_sessions WHERE session_id = %s", (early,)).fetchone()
    assert (ended, reason, status) == (START + 65 * M, "NEXT_BOOKING_AUTO_STOP", "PREPAID_SETTLED")

    prepaid = start_session(db, make_walk_in(db, b, START, 60), b, START, source="WALK_IN")
    db.execute("UPDATE charging_sessions SET prepaid_amount = 100 WHERE session_id = %s", (prepaid,))
    assert one(db, "SELECT auto_stop_sessions(%s)", START + 5 * M) == 0   # 4.5 kWh = ₹90
    assert one(db, "SELECT auto_stop_sessions(%s)", START + 6 * M) == 1   # 5.4 kWh = ₹108: the ₹100 is used up
    assert one(db, "SELECT end_reason FROM charging_sessions WHERE session_id = %s", prepaid) == "PREPAID_USED"


# ---------------------------------------------------------------- the simulator

def test_unplugging_ends_the_session_and_bills_the_time_so_far(db):
    _, [charger] = make_station(db, CCS)
    user = make_user(db)
    booking = make_booking(db, charger, START, 60, status="ACTIVE", user=user, vehicle=make_vehicle(db, user, 100))
    session = start_session(db, booking, charger, START)
    result = one(db, "SELECT simulate_charger_event(%s, 'UNPLUG', %s)", charger, START + 30 * M)
    assert result["accepted"] is True and result["status"] == "AVAILABLE"
    reason, kwh, bill = db.execute("SELECT end_reason, energy_kwh, bill_amount FROM charging_sessions WHERE session_id = %s", (session,)).fetchone()
    assert (reason, kwh, bill) == ("UNPLUGGED", Decimal("27.000"), Decimal("540.00"))
    assert status_of(db, booking) == "COMPLETED"


def test_fault_and_recover(db):
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START, 60, status="ACTIVE")
    session = start_session(db, booking, charger, START)
    assert one(db, "SELECT simulate_charger_event(%s, 'FAULT', %s)", charger, START + 10 * M)["status"] == "FAULTED"
    assert one(db, "SELECT end_reason FROM charging_sessions WHERE session_id = %s", session) == "ADMIN"
    assert one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START + 11 * M)["accepted"] is False
    assert one(db, "SELECT simulate_charger_event(%s, 'RECOVER', %s)", charger, START + 20 * M)["status"] == "AVAILABLE"


def test_events_that_make_no_sense_are_refused_and_logged_not_applied(db):
    _, [charger] = make_station(db, CCS)
    for event, why in [("EXTERNAL_STOP", "No outside session"), ("UNPLUG", "Nothing is charging"), ("RECOVER", None)]:
        result = one(db, "SELECT simulate_charger_event(%s, %s, %s)", charger, event, START)
        if why:
            assert result["accepted"] is False and why in result["reason"]
    assert charger_status(db, charger) == "AVAILABLE"
    with pytest.raises(Exception, match="Unknown event"):
        one(db, "SELECT simulate_charger_event(%s, 'EXPLODE', %s)", charger, START)


def test_every_event_is_logged(db):
    _, [charger] = make_station(db, CCS)
    one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START)
    one(db, "SELECT simulate_charger_event(%s, 'EXTERNAL_START', %s)", charger, START + M)   # refused: already charging
    one(db, "SELECT simulate_charger_event(%s, 'UNPLUG', %s)", charger, START + 5 * M)
    logged = [r[0] for r in db.execute("SELECT event FROM charger_events WHERE charger_id = %s ORDER BY event_id", (charger,))]
    assert logged == ["EXTERNAL_START", "REJECTED_EXTERNAL_START", "EXTERNAL_STOP"]


# ---------------------------------------------------------------- all jobs together

def test_run_due_jobs_runs_everything_and_can_be_limited_to_one_station(db):
    station_a, [a] = make_station(db, CCS)
    _, [b] = make_station(db, CCS)
    stale_a = make_booking(db, a, START + 60 * M, status="HELD", hold_until=START, paid=False)
    stale_b = make_booking(db, b, START + 60 * M, status="HELD", hold_until=START, paid=False)
    result = one(db, "SELECT run_due_jobs(%s, %s)", START + M, station_a)
    assert result["expire_holds"] == 1
    assert (status_of(db, stale_a), status_of(db, stale_b)) == ("EXPIRED", "HELD")  # only the station asked about
    assert one(db, "SELECT run_due_jobs(%s)", START + M)["expire_holds"] == 1
    assert status_of(db, stale_b) == "EXPIRED"
    assert set(one(db, "SELECT run_due_jobs(%s)", START + 2 * M)) == {
        "expire_holds", "resolve_occupied_starts", "mark_no_shows", "auto_stop_sessions", "apply_reservation_locks"}


def test_a_whole_booking_story_without_touching_anything(db):
    """A booking nobody claims: reserved, then no-show, then free: all by itself as time passes."""
    _, [charger] = make_station(db, CCS)
    booking = make_booking(db, charger, START)
    for minutes, charger_expected, booking_expected in [(-20, "AVAILABLE", "CONFIRMED"), (-15, "RESERVED", "CONFIRMED"),
                                                       (9, "RESERVED", "CONFIRMED"), (10, "AVAILABLE", "NO_SHOW")]:
        one(db, "SELECT run_due_jobs(%s)", START + minutes * M)
        assert (charger_status(db, charger), status_of(db, booking)) == (charger_expected, booking_expected), minutes


# ---------------------------------------------------------------- realtime nudges

def test_changes_send_a_nudge_with_only_the_station_and_charger(db):
    """Realtime exists only on Supabase, so the test makes a stand-in `realtime.send` that records its calls."""
    db.execute("CREATE SCHEMA IF NOT EXISTS realtime")
    db.execute("CREATE TEMP TABLE sent (payload jsonb, event text, topic text, private boolean)")
    db.execute(
        "CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) RETURNS void "
        "LANGUAGE sql AS $$ INSERT INTO pg_temp.sent VALUES (payload, event, topic, private) $$"
    )
    station, [charger] = make_station(db, CCS)
    db.execute("DELETE FROM sent")

    booking = make_booking(db, charger, START)
    rows = db.execute("SELECT payload, event, topic, private FROM sent").fetchall()
    assert rows, "a new booking should send a nudge"
    for payload, event, topic, private in rows:
        assert payload == {"station_id": str(station), "charger_id": str(charger)}  # nothing about the booking or the driver
        assert (event, topic, private) == ("changed", f"station:{station}", False)

    db.execute("DELETE FROM sent")
    conn_status = one(db, "SELECT simulate_charger_event(%s, 'FAULT', %s)", charger, START)
    assert conn_status["status"] == "FAULTED"
    assert any(topic == f"station:{station}" for _, _, topic, _ in db.execute("SELECT payload, event, topic, private FROM sent").fetchall())
    assert booking


def test_a_broken_realtime_never_breaks_a_booking(db):
    db.execute("CREATE SCHEMA IF NOT EXISTS realtime")
    db.execute("CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) RETURNS void "
               "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'realtime is down'; END $$")
    _, [charger] = make_station(db, CCS)
    assert make_booking(db, charger, START)  # still works


# ---------------------------------------------------------------- the energy formula

def test_energy_formula_examples(db):
    def energy(power, minutes, battery=None, soc=None):
        return one(db, "SELECT session_energy_kwh(%s, %s, %s, %s, %s)", power, START, START + minutes * M, battery, soc)

    assert energy(60, 60) == Decimal("32.000")           # 54 kWh of charging, but the default 40 kWh battery at 20% has room for 32
    assert energy(60, 60, battery=100) == Decimal("54.000")
    assert energy(7, 30) == Decimal("3.150")
    assert energy(60, 0) == Decimal("0.000")
    assert energy(None, 60) == Decimal("0.000")           # a charger with no known power delivers nothing we can count
    assert energy(60, 600, battery=100, soc=90) == Decimal("10.000")
    assert one(db, "SELECT session_bill_amount(%s, %s)", Decimal("12.345"), Decimal("17.5")) == Decimal("216.04")
    assert one(db, "SELECT session_bill_amount(%s, NULL)", Decimal("12")) == Decimal("0.00")
