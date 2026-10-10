"""Demo data so ChargeSpot looks alive: demo accounts, cars, bookings and kiosk devices.

- One demo admin and 15 demo drivers (emails @chargespot.test), each with a car.
- Bookings on every four-wheeler charger within 25 km of Ahmedabad, from 3 days ago to
  6 days ahead, 08:00-22:00 IST: past ones COMPLETED (with a charging session and paid
  bill), NO_SHOW or CANCELLED; future ones CONFIRMED or CANCELLED.
- A kiosk device for three of the hand-verified Ahmedabad stations.

Every booking goes through the real status rules (HELD -> CONFIRMED -> ...), so the
database checks all of it. Choices are random but seeded, so a re-run on the same day
gives the same result. Re-running replaces the demo bookings and keeps everything else.

The demo password and kiosk keys are printed ONCE, when created. They are stored only as
hashes. Lost them? Re-issue without touching bookings:
    python -m database.seeds.demo_data --reset-password --new-kiosk-keys

Usage (repository root, backend venv active):
    python -m database.seeds.demo_data
"""

import argparse
import hashlib
import os
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone

import bcrypt

from database.common import connect
from database.seeds.profiles import rng_for

# India has no daylight saving time, so a fixed +05:30 offset is exact (and needs no tz database).
IST = timezone(timedelta(hours=5, minutes=30))
AHMEDABAD = (23.0225, 72.5714)
RADIUS_KM = 25

DEMO_DOMAIN = "chargespot.test"
ADMIN = (f"demo.admin@{DEMO_DOMAIN}", "Demo Admin")
DRIVER_NAMES = ["Aarav Shah", "Diya Patel", "Kabir Mehta", "Isha Desai", "Vihaan Joshi", "Anaya Trivedi",
                "Reyansh Bhatt", "Myra Parikh", "Arjun Modi", "Saanvi Pandya", "Vivaan Dave", "Kiara Vyas",
                "Aditya Thakkar", "Riya Chauhan", "Krish Solanki"]
CARS = [("Tata Nexon EV", "CCS2", 40.5), ("MG ZS EV", "CCS2", 50.3), ("Tata Tiago EV", "CCS2", 24.0),
        ("Hyundai Kona Electric", "CCS2", 39.2), ("Mahindra XUV400", "CCS2", 39.4), ("BYD Atto 3", "CCS2", 60.5)]

DAYS_BACK, DAYS_AHEAD = 3, 7              # bookings from 3 days ago up to 6 days ahead
OPEN, CLOSE = time(8, 0), time(22, 0)     # IST
SLOT = timedelta(minutes=30)
BOOKING_CHANCE = 0.22                     # chance a free 30-minute slot starts a booking
BLOCK_WEIGHTS = {1: 2, 2: 3, 3: 2, 4: 1}  # booking length in slots
FEE = 199
EFFICIENCY = 0.9


def ensure_users(conn, reset_password: bool) -> tuple[str, list[tuple[str, str]], str | None]:
    """Create demo accounts if missing. Returns (admin_id, [(driver_id, vehicle_id)], new_password)."""
    people = [(ADMIN[0], ADMIN[1], "ADMIN")] + [
        (f"demo.driver{i + 1:02d}@{DEMO_DOMAIN}", name, "USER") for i, name in enumerate(DRIVER_NAMES)
    ]
    existing = {email: uid for uid, email in conn.execute(
        "SELECT user_id::text, email FROM users WHERE email LIKE %s", (f"%@{DEMO_DOMAIN}",))}
    missing = [p for p in people if p[0] not in existing]

    password = None
    if missing or reset_password:
        password = os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(9)
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        for email, name, role in missing:
            existing[email] = conn.execute(
                "INSERT INTO users (email, full_name, role, password_hash) VALUES (%s, %s, %s, %s) RETURNING user_id::text",
                (email, name, role, password_hash),
            ).fetchone()[0]
        if reset_password:
            conn.execute("UPDATE users SET password_hash = %s WHERE email LIKE %s", (password_hash, f"%@{DEMO_DOMAIN}"))

    drivers = []
    for i, (email, _, role) in enumerate(people[1:]):
        uid = existing[email]
        vehicle = conn.execute("SELECT vehicle_id::text FROM vehicles WHERE user_id = %s AND is_default", (uid,)).fetchone()
        if not vehicle:
            model, connector, battery = CARS[i % len(CARS)]
            vehicle = conn.execute(
                "INSERT INTO vehicles (user_id, nickname, connector_type, battery_kwh, is_default) "
                "VALUES (%s, %s, %s, %s, true) RETURNING vehicle_id::text",
                (uid, model, connector, battery),
            ).fetchone()
        drivers.append((uid, vehicle[0]))
    return existing[ADMIN[0]], drivers, password


def remove_demo_bookings(conn, user_ids: list[str]) -> None:
    demo = "SELECT booking_id FROM bookings WHERE user_id = ANY(%s::uuid[])"
    conn.execute(f"DELETE FROM payments WHERE booking_id IN ({demo})", (user_ids,))
    conn.execute(f"DELETE FROM charging_sessions WHERE booking_id IN ({demo})", (user_ids,))
    conn.execute("DELETE FROM bookings WHERE user_id = ANY(%s::uuid[])", (user_ids,))


def demo_chargers(conn) -> list[tuple[str, float, float]]:
    return conn.execute(
        """
        SELECT c.charger_id::text, c.power_kw::float, c.price_per_kwh::float
        FROM chargers c JOIN stations s USING (station_id)
        WHERE s.vehicle_category = 'FOUR_WHEELER' AND s.is_active AND c.status = 'AVAILABLE'
          AND c.power_kw IS NOT NULL AND c.price_per_kwh IS NOT NULL
          AND haversine_km(s.latitude, s.longitude, %s, %s) <= %s
        ORDER BY c.charger_id
        """,
        (*AHMEDABAD, RADIUS_KM),
    ).fetchall()


def plan_slots(charger_id: str, today: date) -> list[tuple[datetime, datetime]]:
    """Random but repeatable bookings for one charger, as (start, end) in IST."""
    slots = []
    for offset in range(-DAYS_BACK, DAYS_AHEAD):
        day = today + timedelta(days=offset)
        rng = rng_for(charger_id, f"bookings:{day.isoformat()}")
        t, close = datetime.combine(day, OPEN, IST), datetime.combine(day, CLOSE, IST)
        while t < close:
            if rng.random() < BOOKING_CHANCE:
                blocks = rng.choices(list(BLOCK_WEIGHTS), weights=list(BLOCK_WEIGHTS.values()))[0]
                end = min(t + blocks * SLOT, close)
                slots.append((t, end))
                t = end
            else:
                t += SLOT
    return slots


def build_bookings(chargers, drivers, now: datetime) -> list[dict]:
    bookings = []
    for charger_id, power, price in chargers:
        for start, end in plan_slots(charger_id, now.astimezone(IST).date()):
            if start < now < end:
                continue   # skip slots in progress: live charging is simulated from Phase 5
            rng = rng_for(charger_id, f"outcome:{start.isoformat()}")
            roll = rng.random()
            if end <= now:
                outcome = "COMPLETED" if roll < 0.80 else "NO_SHOW" if roll < 0.92 else "CANCELLED"
            else:
                outcome = "CONFIRMED" if roll < 0.92 else "CANCELLED"
            user_id, vehicle_id = drivers[len(bookings) % len(drivers)]
            bookings.append({
                "booking_id": str(uuid.uuid4()), "user_id": user_id, "vehicle_id": vehicle_id,
                "charger_id": charger_id, "start": start, "end": end, "outcome": outcome,
                "power": power, "price": price, "rng": rng,
            })
    return bookings


def insert_bookings(conn, bookings: list[dict], drivers_count: int, batteries: dict[str, float], now: datetime) -> None:
    conn.execute("SELECT set_config('chargespot.actor', 'SYSTEM', true), set_config('chargespot.reason', 'demo data', true)")

    # A user may hold only one unpaid slot at a time, so insert in waves with one booking per
    # driver, then confirm the wave before the next one.
    for i in range(0, len(bookings), drivers_count):
        wave = bookings[i:i + drivers_count]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO bookings (booking_id, user_id, vehicle_id, charger_id, source, status, time_range, "
                "hold_expires_at, booking_fee) VALUES (%s, %s, %s, %s, 'APP', 'HELD', tstzrange(%s, %s, '[)'), %s, %s)",
                [(b["booking_id"], b["user_id"], b["vehicle_id"], b["charger_id"], b["start"], b["end"],
                  min(now, b["start"]) + timedelta(minutes=5), FEE) for b in wave],
            )
        conn.execute("UPDATE bookings SET status = 'CONFIRMED' WHERE booking_id = ANY(%s::uuid[])",
                     ([b["booking_id"] for b in wave],))

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO payments (booking_id, purpose, provider_order_id, provider_payment_id, amount, status) "
            "VALUES (%s, 'BOOKING_FEE', %s, %s, %s, 'CAPTURED')",
            [(b["booking_id"], f"demo_order_{b['booking_id']}", f"demo_pay_{b['booking_id']}", FEE) for b in bookings],
        )

    by_outcome = {o: [b for b in bookings if b["outcome"] == o] for o in ("COMPLETED", "NO_SHOW", "CANCELLED")}

    completed = by_outcome["COMPLETED"]
    ids = [b["booking_id"] for b in completed]
    conn.execute("UPDATE bookings SET status = 'ACTIVE', otp_used_at = lower(time_range) WHERE booking_id = ANY(%s::uuid[])", (ids,))
    conn.execute("UPDATE bookings SET status = 'COMPLETED' WHERE booking_id = ANY(%s::uuid[])", (ids,))
    sessions = []
    for b in completed:
        rng = b["rng"]
        started = b["start"] + timedelta(minutes=rng.randint(0, 8))
        ended = b["end"] - timedelta(minutes=rng.randint(0, 10))
        start_soc = rng.randint(10, 45)
        room = batteries[b["vehicle_id"]] * (100 - start_soc) / 100
        energy = round(min(b["power"] * (ended - started).total_seconds() / 3600 * EFFICIENCY, room), 3)
        bill = round(energy * b["price"], 2)
        reason = "SLOT_END_AUTO_STOP" if ended >= b["end"] - timedelta(minutes=1) else "USER_STOP"
        sessions.append((str(uuid.uuid4()), b["booking_id"], b["charger_id"], started, ended, reason, start_soc,
                         energy, bill, ended + timedelta(minutes=5)))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO charging_sessions (session_id, booking_id, charger_id, source, started_at, ended_at, end_reason, "
            "start_soc_percent, energy_kwh, bill_amount, bill_status, paid_at) "
            "VALUES (%s, %s, %s, 'BOOKING', %s, %s, %s, %s, %s, %s, 'PAID', %s)",
            sessions,
        )
        cur.executemany(
            "INSERT INTO payments (booking_id, session_id, purpose, provider_order_id, provider_payment_id, amount, status) "
            "VALUES (%s, %s, 'ENERGY', %s, %s, %s, 'CAPTURED')",
            [(s[1], s[0], f"demo_order_{s[0]}", f"demo_pay_{s[0]}", s[8]) for s in sessions if s[8] > 0],
        )

    no_shows = [b["booking_id"] for b in by_outcome["NO_SHOW"]]
    conn.execute("UPDATE bookings SET status = 'NO_SHOW' WHERE booking_id = ANY(%s::uuid[])", (no_shows,))

    cancelled = [b["booking_id"] for b in by_outcome["CANCELLED"]]
    conn.execute(
        "UPDATE bookings SET status = 'CANCELLED', cancelled_at = lower(time_range) - interval '1 day', "
        "cancel_reason = 'Plans changed', refund_amount = %s WHERE booking_id = ANY(%s::uuid[])",
        (FEE, cancelled),
    )
    conn.execute(
        "UPDATE payments SET status = 'REFUNDED', refunded_amount = amount "
        "WHERE purpose = 'BOOKING_FEE' AND booking_id = ANY(%s::uuid[])",
        (cancelled,),
    )


def ensure_kiosk_devices(conn, new_keys_for_all: bool = False) -> list[str]:
    """One kiosk for each of three hand-verified Ahmedabad stations. Returns newly created keys.

    With new_keys_for_all, existing demo kiosks are switched off and replaced, so lost
    keys can be re-issued (the old keys stop working).
    """
    stations = conn.execute(
        """
        SELECT s.station_id, s.name FROM stations s
        WHERE s.data_source = 'manual' AND s.vehicle_category = 'FOUR_WHEELER'
          AND haversine_km(s.latitude, s.longitude, %s, %s) <= %s
        ORDER BY s.name LIMIT 3
        """,
        (*AHMEDABAD, RADIUS_KM),
    ).fetchall()
    new_keys = []
    for station_id, name in stations:
        if new_keys_for_all:
            conn.execute("UPDATE station_devices SET is_active = false WHERE station_id = %s", (station_id,))
        elif conn.execute("SELECT 1 FROM station_devices WHERE station_id = %s AND is_active", (station_id,)).fetchone():
            continue
        prefix = "ks_" + secrets.token_hex(4)
        key = f"{prefix}_{secrets.token_urlsafe(24)}"
        conn.execute(
            "INSERT INTO station_devices (station_id, name, key_prefix, api_key_hash) VALUES (%s, %s, %s, %s)",
            (station_id, f"Kiosk – {name}", prefix, hashlib.sha256(key.encode()).hexdigest()),
        )
        new_keys.append(f"{name}: {key}")
    return new_keys


def issue_secrets(reset_password: bool, new_kiosk_keys: bool) -> list[str]:
    """Only re-issue the demo password and/or kiosk keys, without touching bookings."""
    with connect() as conn:
        _, _, password = ensure_users(conn, reset_password)
        keys = ensure_kiosk_devices(conn, new_keys_for_all=new_kiosk_keys) if new_kiosk_keys else []
        conn.commit()
    shown = [f"Demo password for every @{DEMO_DOMAIN} account (admin: {ADMIN[0]}): {password}"] if password else []
    return shown + [f"Kiosk key – {k}" for k in keys]


def run(reset_password: bool = False) -> tuple[str, list[str]]:
    """Returns (summary, secrets_to_show_once)."""
    now = datetime.now(timezone.utc)
    with connect() as conn:
        admin_id, drivers, password = ensure_users(conn, reset_password)
        driver_ids = [d[0] for d in drivers]
        batteries = dict(conn.execute(
            "SELECT vehicle_id::text, battery_kwh::float FROM vehicles WHERE user_id = ANY(%s::uuid[])", (driver_ids,)
        ).fetchall())
        remove_demo_bookings(conn, driver_ids)
        chargers = demo_chargers(conn)
        bookings = build_bookings(chargers, drivers, now)
        insert_bookings(conn, bookings, len(drivers), batteries, now)
        keys = ensure_kiosk_devices(conn)
        conn.commit()

    counts = {o: sum(1 for b in bookings if b["outcome"] == o) for o in ("CONFIRMED", "COMPLETED", "NO_SHOW", "CANCELLED")}
    secrets_out = []
    if password:
        secrets_out.append(f"Demo password for every @{DEMO_DOMAIN} account (admin: {ADMIN[0]}): {password}")
    secrets_out += [f"Kiosk key – {k}" for k in keys]
    summary = (f"Demo data: {len(drivers)} drivers + 1 admin; {len(bookings)} bookings on {len(chargers)} Ahmedabad "
               f"chargers {counts}; {len(keys)} new kiosk device(s).")
    return summary, secrets_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Create demo accounts, bookings and kiosk devices.")
    parser.add_argument("--reset-password", action="store_true", help="give every demo account a new password")
    parser.add_argument("--new-kiosk-keys", action="store_true", help="replace the demo kiosks' keys")
    args = parser.parse_args()
    if args.reset_password or args.new_kiosk_keys:
        summary, shown_once = "Re-issued demo secrets (bookings unchanged).", issue_secrets(args.reset_password, args.new_kiosk_keys)
    else:
        summary, shown_once = run()
    print(summary)
    if shown_once:
        print("\nSave these now. They are shown only once and stored only as hashes:")
        for line in shown_once:
            print("  " + line)


if __name__ == "__main__":
    main()
