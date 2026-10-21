"""Demo helper: make chargers and bookings do things, without an admin page or a login token.

Run from the backend folder with the virtual environment active:

    python -m scripts.simulate list "tata"                     chargers whose station name contains "tata"
    python -m scripts.simulate bookings you@example.com        that driver's upcoming bookings, with ids
    python -m scripts.simulate event EXTERNAL_START "Riya" CCS2-1
                                                               an outside driver starts that charger
    python -m scripts.simulate event UNPLUG "Riya" CCS2-1      also EXTERNAL_STOP, FAULT, RECOVER
    python -m scripts.simulate start <booking-id>              start charging for a booking, like the kiosk will
    python -m scripts.simulate jobs                            run all background jobs once, right now

It talks to the database in DATABASE_URL (the live Supabase one if that is what backend/.env says).
"""

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.db import SessionLocal
from app.features.chargers import service as simulator
from app.features.charging import service as charging
from app.features.jobs.lazy import run_due_jobs

EVENTS = simulator.EVENTS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _find_charger(db, station_part: str, label: str | None):
    rows = db.execute(
        text(
            "SELECT c.charger_id, s.name, c.label, c.status FROM chargers c JOIN stations s USING (station_id) "
            "WHERE s.name ILIKE :s AND (CAST(:l AS text) IS NULL OR c.label ILIKE :l) AND s.vehicle_category = 'FOUR_WHEELER' "
            "ORDER BY s.name, c.label LIMIT 20"
        ),
        {"s": f"%{station_part}%", "l": label},
    ).all()
    if not rows:
        sys.exit(f"No charger found for station containing '{station_part}'" + (f" and label '{label}'." if label else "."))
    if len(rows) > 1 and not label:
        print("More than one charger matches; add the label (for example CCS2-1):")
        for row in rows:
            print(f"  {row.name}  {row.label}  [{row.status}]")
        sys.exit(1)
    if len(rows) > 1:
        print("More than one charger matches; be more specific:")
        for row in rows:
            print(f"  {row.name}  {row.label}  [{row.status}]")
        sys.exit(1)
    return rows[0]


def cmd_list(db, args):
    rows = db.execute(
        text(
            "SELECT s.name, c.label, c.connector_type, c.power_kw, c.status, c.charger_id FROM chargers c JOIN stations s USING (station_id) "
            "WHERE s.name ILIKE :s AND s.vehicle_category = 'FOUR_WHEELER' ORDER BY s.name, c.label LIMIT 40"
        ),
        {"s": f"%{args.station}%"},
    ).all()
    for r in rows:
        print(f"{r.name:40.40}  {r.label:10}  {r.connector_type:13}  {str(r.power_kw) + ' kW':>9}  {r.status:14}  {r.charger_id}")
    print(f"{len(rows)} charger(s)")


def cmd_bookings(db, args):
    rows = db.execute(
        text(
            "SELECT b.booking_id, s.name, c.label, b.status, lower(b.time_range) AT TIME ZONE 'Asia/Kolkata' AS starts, "
            "(SELECT session_id FROM charging_sessions WHERE booking_id = b.booking_id) AS session_id "
            "FROM bookings b JOIN users u USING (user_id) JOIN chargers c USING (charger_id) JOIN stations s USING (station_id) "
            "WHERE lower(u.email) = lower(:e) AND b.status IN ('HELD', 'CONFIRMED', 'ACTIVE') AND upper(b.time_range) > now() "
            "ORDER BY lower(b.time_range) LIMIT 20"
        ),
        {"e": args.email},
    ).all()
    for r in rows:
        print(f"{r.booking_id}  {r.status:9}  {r.starts:%a %d %b %H:%M} IST  {r.name} · {r.label}" + (f"  session {r.session_id}" if r.session_id else ""))
    print(f"{len(rows)} upcoming booking(s)")


def cmd_event(db, args):
    charger = _find_charger(db, args.station, args.label)
    print(f"{args.event} on {charger.name} · {charger.label} (was {charger.status})")
    result = simulator.simulate(db, charger.charger_id, args.event, _now())
    print("accepted" if result["accepted"] else "REFUSED", "->", result["status"], ("- " + result["reason"]) if result.get("reason") else "")


def cmd_start(db, args):
    session = charging.start_session(db, args.booking_id, _now(), actor="ADMIN")
    print(f"Charging started. Live page: /charging/{session.session_id}")


def cmd_jobs(db, _args):
    print(run_due_jobs(db, _now()))


def main() -> None:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # station names have dashes the Windows console cannot print
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list"); p.add_argument("station", nargs="?", default=""); p.set_defaults(run=cmd_list)
    p = sub.add_parser("bookings"); p.add_argument("email"); p.set_defaults(run=cmd_bookings)
    p = sub.add_parser("event"); p.add_argument("event", choices=EVENTS); p.add_argument("station"); p.add_argument("label", nargs="?"); p.set_defaults(run=cmd_event)
    p = sub.add_parser("start"); p.add_argument("booking_id"); p.set_defaults(run=cmd_start)
    p = sub.add_parser("jobs"); p.set_defaults(run=cmd_jobs)
    args = parser.parse_args()
    with SessionLocal() as db:
        args.run(db, args)


if __name__ == "__main__":
    main()
