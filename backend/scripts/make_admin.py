"""Make an existing account an admin (admins can use the simulator endpoints).

    python -m scripts.make_admin you@example.com            (run from the backend folder)
    python -m scripts.make_admin you@example.com --remove   back to an ordinary driver
"""

import argparse
import sys

from sqlalchemy import text

from app.db import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--remove", action="store_true", help="make the account an ordinary driver again")
    args = parser.parse_args()
    role = "USER" if args.remove else "ADMIN"
    with SessionLocal() as db:
        found = db.execute(
            text("UPDATE users SET role = :r WHERE lower(email) = lower(:e) RETURNING email"), {"r": role, "e": args.email}
        ).scalar()
        db.commit()
    if not found:
        sys.exit(f"No account with the email {args.email}. Sign in once first so the account exists.")
    print(f"{found} is now {role}.")


if __name__ == "__main__":
    main()
