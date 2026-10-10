"""One-off: copy user accounts from the old local database to the new one.

Keeps each user's ID, email, name, Google ID, password hash and role, so existing
Google and email logins keep working (and tokens issued before the move stay valid).
Test accounts from early development are skipped. Safe to re-run: existing users are
updated, not duplicated.

Usage (repository root, backend venv active):
    python -m database.imports.migrate_users
"""

from database.common import connect

# Throwaway accounts created while testing the old app.
SKIP_EMAIL_PATTERNS = ("%@example.com", "ji@gmail.com")


def run() -> str:
    with connect("LEGACY_DATABASE_URL") as old:
        users = old.execute(
            "SELECT user_id, email, full_name, phone, google_user_id, password_hash, role, created_at "
            "FROM users WHERE NOT (lower(email) LIKE ANY(%s))",
            (list(SKIP_EMAIL_PATTERNS),),
        ).fetchall()
        skipped = old.execute("SELECT count(*) FROM users").fetchone()[0] - len(users)

    with connect() as new:
        for u in users:
            new.execute(
                """
                INSERT INTO users (user_id, email, full_name, phone, google_user_id, password_hash, role, created_at)
                VALUES (%s, lower(%s), %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    email = EXCLUDED.email, full_name = EXCLUDED.full_name, phone = EXCLUDED.phone,
                    google_user_id = EXCLUDED.google_user_id, password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role
                """,
                (u[0], u[1], u[2], u[3], u[4], u[5], u[6] if u[6] in ("USER", "ADMIN") else "USER", u[7]),
            )
        new.commit()
    return f"Users: copied {len(users)}, skipped {skipped} test account(s)."


if __name__ == "__main__":
    print(run())
