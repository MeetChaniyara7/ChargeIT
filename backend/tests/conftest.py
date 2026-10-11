"""Shared test setup.

Settings are set *before* the app is imported, so tests never touch the real database or
real secrets (the .env file never overrides variables that are already set).

Two kinds of tests:
- Most need NO database (pure logic, or the API with its database call faked).
- Tests marked `needs_db` use TEST_DATABASE_URL: a throwaway LOCAL PostgreSQL database
  from backend/.env. It is wiped and rebuilt from database/migrations once per test run,
  and every test runs inside a transaction that is rolled back afterwards. They are
  skipped when TEST_DATABASE_URL is not set.
"""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(REPO_ROOT))  # so tests can import the `database` package (migrations)

os.environ.update(
    {
        # Port 1 is never a real database: any accidental query fails fast instead of
        # touching real data.
        "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:1/chargespot_test",
        "JWT_SECRET_KEY": "test-secret-key-that-is-only-used-in-tests",
        "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        "GOOGLE_REDIRECT_URI": "http://testserver/auth/google/callback",
        "FRONTEND_URL": "http://localhost:5173",
        "CORS_ORIGINS": "http://localhost:5173",
    }
)
# Only this one value is taken from backend/.env.
_test_db_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND_DIR / ".env").get("TEST_DATABASE_URL")
if _test_db_url:
    os.environ["TEST_DATABASE_URL"] = _test_db_url

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import get_db  # noqa: E402
from app.features.auth.dependencies import get_current_user  # noqa: E402
from app.features.auth.models import User  # noqa: E402
from app.main import app  # noqa: E402

HAS_TEST_DB = bool(os.environ.get("TEST_DATABASE_URL"))
needs_db = pytest.mark.skipif(not HAS_TEST_DB, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def test_engine():
    """The throwaway database with the real schema."""
    if not HAS_TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set")
    from database import common
    from database.migrate import apply_pending, reset_schema

    with common.connect("TEST_DATABASE_URL") as conn:
        reset_schema(conn)
        apply_pending(conn, verbose=False)
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine):
    """A database session whose changes are rolled back after the test (commits become savepoints)."""
    connection = test_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def db_client(client, db):
    """The API wired to the test database, with a signed-in ordinary user."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: User(
        user_id="11111111-1111-1111-1111-111111111111", email="driver@test.dev", role="USER"
    )
    return client
