"""Apply database migrations in order.

Each file in database/migrations/ (001_..., 002_..., ...) runs once, inside its own
transaction: either the whole file applies or none of it does. Applied files are
recorded in the schema_migrations table, so running this again only applies new ones.

Usage (from the repository root, backend virtual environment active):
    python -m database.migrate            # apply pending migrations to DATABASE_URL
    python -m database.migrate --status   # list applied and pending migrations
    python -m database.migrate --env TEST_DATABASE_URL --reset   # wipe and rebuild the TEST database
"""

import argparse
from pathlib import Path

import psycopg

from database.common import connect

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# --reset deletes every table. It is only ever allowed on the throwaway test database.
RESETTABLE_ENVS = {"TEST_DATABASE_URL"}


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def ensure_tracking_table(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    conn.commit()


def applied_versions(conn: psycopg.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def reset_schema(conn: psycopg.Connection) -> None:
    """Drop and recreate the public schema (test database only)."""
    conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
    conn.execute("CREATE SCHEMA public")
    # Domains and functions created by migrations live in public, so they go too.
    conn.commit()


def apply_pending(conn: psycopg.Connection, verbose: bool = True) -> list[str]:
    ensure_tracking_table(conn)
    done = applied_versions(conn)
    applied = []
    for path in migration_files():
        version = path.stem
        if version in done:
            continue
        if verbose:
            print(f"Applying {path.name} ...")
        with conn.transaction():
            # No parameters, so psycopg sends the whole file as one script.
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        applied.append(version)
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", default="DATABASE_URL", help="environment variable holding the database URL")
    parser.add_argument("--status", action="store_true", help="only list applied and pending migrations")
    parser.add_argument("--reset", action="store_true", help="wipe the schema first (TEST database only)")
    args = parser.parse_args()

    if args.reset and args.env not in RESETTABLE_ENVS:
        raise SystemExit(f"--reset is only allowed with --env {' / '.join(RESETTABLE_ENVS)}. Refusing to wipe {args.env}.")

    with connect(args.env) as conn:
        if args.reset:
            reset_schema(conn)
            print("Schema wiped.")
        ensure_tracking_table(conn)

        if args.status:
            done = applied_versions(conn)
            for path in migration_files():
                print(f"  [{'x' if path.stem in done else ' '}] {path.name}")
            return

        applied = apply_pending(conn)
        print(f"Done. {len(applied)} migration(s) applied." if applied else "Database is already up to date.")


if __name__ == "__main__":
    main()
