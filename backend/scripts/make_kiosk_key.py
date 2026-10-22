"""Make a key for a station's kiosk tablet (until the admin pages of Phase 7 can do it).

    python -m scripts.make_kiosk_key "Riya Autolink Sola"                  (run from the backend folder)
    python -m scripts.make_kiosk_key "Riya" --name "Entrance kiosk"

The key is printed once. Copy it to the tablet's setup screen: only a hash of it is stored, so it cannot be shown again.
It writes to the database in DATABASE_URL (the live Supabase one if that is what backend/.env says).
"""

import argparse
import sys

from sqlalchemy import text

from app.db import SessionLocal
from app.features.kiosk.admin_router import create_device


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("station", help="part of the station's name")
    parser.add_argument("--name", default="Station kiosk", help="a label for the tablet")
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT station_id, name, city FROM stations WHERE name ILIKE :s AND vehicle_category = 'FOUR_WHEELER' ORDER BY name LIMIT 10"),
            {"s": f"%{args.station}%"},
        ).all()
        if not rows:
            sys.exit(f"No station with a name containing '{args.station}'.")
        if len(rows) > 1:
            print("More than one station matches; use more of the name:")
            for row in rows:
                print(f"  {row.name} ({row.city})")
            sys.exit(1)
        station = rows[0]
        station_name = station.name  # read inside the session: create_device commits, which expires loaded objects
        _, key = create_device(db, station.station_id, args.name)
    print(f"Kiosk '{args.name}' created for {station_name}.")
    print(f"Key (shown only now): {key}")


if __name__ == "__main__":
    main()
