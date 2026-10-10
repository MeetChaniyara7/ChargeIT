"""Shared test setup.

Test settings are set *before* the app is imported, so the tests never touch the real
database or real secrets (the .env file never overrides variables that are already set).
"""

import os

os.environ.update(
    {
        # Port 1 is never a real database: any accidental query fails fast instead of
        # touching real data. Phase 1 tests need no database at all.
        "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:1/chargespot_test",
        "JWT_SECRET_KEY": "test-secret-key-that-is-only-used-in-tests",
        "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        "GOOGLE_REDIRECT_URI": "http://testserver/auth/google/callback",
        "FRONTEND_URL": "http://localhost:5173",
        "CORS_ORIGINS": "http://localhost:5173",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()
