"""Build the whole database in the right order, with one command.

Steps:
  1. migrate          create or upgrade the schema
  2. users            copy accounts from the old local database (skipped if LEGACY_DATABASE_URL is unset)
  3. manual           the 10 hand-verified Ahmedabad stations
  4. osm              OpenStreetMap stations in the region
  5. ocm              Open Charge Map stations in the region
  6. dedupe           merge duplicate stations
  7. synthetic        fill missing chargers, power, prices and ratings (labelled)
  8. demo             demo accounts, a week of bookings, kiosk devices

Every step is safe to re-run.

Usage (repository root, backend venv active):
    python -m database.pipeline                    # everything, using cached downloads
    python -m database.pipeline --refresh          # download fresh station data first
    python -m database.pipeline --fresh-stations   # delete all stations and re-import them
                                                   # (refused if any real booking exists)
"""

import argparse
import os

from database.common import connect
from database.imports import dedupe, import_legacy_manual, import_ocm, import_osm, migrate_users
from database.migrate import apply_pending
from database.seeds import demo_data, synthetic


def delete_station_data() -> str:
    """Remove every station so imports start from scratch. Only demo bookings may exist."""
    with connect() as conn:
        real = conn.execute(
            "SELECT count(*) FROM bookings b LEFT JOIN users u USING (user_id) "
            "WHERE u.email IS NULL OR u.email NOT LIKE %s",
            (f"%@{demo_data.DEMO_DOMAIN}",),
        ).fetchone()[0]
        if real:
            raise SystemExit(f"Refusing --fresh-stations: {real} real booking(s) exist and point at chargers.")
        demo_ids = [r[0] for r in conn.execute("SELECT user_id::text FROM users WHERE email LIKE %s",
                                               (f"%@{demo_data.DEMO_DOMAIN}",))]
        demo_data.remove_demo_bookings(conn, demo_ids)
        conn.execute("DELETE FROM charging_sessions")      # only EXTERNAL ones can remain
        conn.execute("DELETE FROM station_devices")
        conn.execute("DELETE FROM stations")               # chargers and station_sources go with them
        conn.execute("DELETE FROM operators")
        conn.commit()
    return "Fresh start: all stations, chargers, operators and kiosk devices deleted."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="download fresh station data")
    parser.add_argument("--fresh-stations", action="store_true", help="delete all stations and re-import")
    args = parser.parse_args()

    with connect() as conn:
        applied = apply_pending(conn, verbose=False)
    print(f"1. Schema: {len(applied)} migration(s) applied." if applied else "1. Schema: up to date.")

    if args.fresh_stations:
        print("   " + delete_station_data())

    if os.getenv("LEGACY_DATABASE_URL"):
        print("2. " + migrate_users.run())
    else:
        print("2. Users: skipped (LEGACY_DATABASE_URL not set).")
    print("3. " + import_legacy_manual.run())
    print("4. " + import_osm.run(args.refresh))
    print("5. " + import_ocm.run(args.refresh))
    print("6. " + dedupe.run())
    print("7. " + synthetic.run())
    summary, shown_once = demo_data.run()
    print("8. " + summary)

    with connect() as conn:
        rows = conn.execute(
            "SELECT data_source, vehicle_category, count(*) FROM stations GROUP BY 1, 2 ORDER BY 1, 2"
        ).fetchall()
        chargers = conn.execute("SELECT data_source, count(*) FROM chargers GROUP BY 1 ORDER BY 1").fetchall()
    print("\nStations by source:", ", ".join(f"{src}/{cat.lower().replace('_', '-')}: {n}" for src, cat, n in rows))
    print("Chargers by source:", ", ".join(f"{src}: {n}" for src, n in chargers))

    if shown_once:
        print("\nSave these now. They are shown only once and stored only as hashes:")
        for line in shown_once:
            print("  " + line)


if __name__ == "__main__":
    main()
