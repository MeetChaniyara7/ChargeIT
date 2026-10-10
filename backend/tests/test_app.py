"""App-level behaviour: health check, error format, removed routes, admin protection."""

import pytest

from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ChargeSpot API"


# These old routes leaked user data or let anyone write. They must stay gone.
@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/api/users"),
        ("POST", "/api/users/sync"),
        ("GET", "/api/reservations/user/00000000-0000-0000-0000-000000000000"),
        ("POST", "/api/reservations"),
        ("GET", "/api/sessions/user/00000000-0000-0000-0000-000000000000"),
        ("POST", "/api/sessions"),
        ("GET", "/api/chargers"),
        ("GET", "/api/connectors"),
        ("GET", "/api/operators"),
    ],
)
def test_removed_routes_return_404(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}


def test_validation_errors_use_standard_format(client):
    response = client.post("/auth/login", json={"email": "a@b.c"})  # password missing
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "password" in response.json()["error"]["message"]


def _as_user(role: str) -> User:
    return User(user_id="11111111-1111-1111-1111-111111111111", email="u@test.dev", role=role)


NEW_STATION = {"name": "Test", "address": "Somewhere", "latitude": 23.0, "longitude": 72.5}


def test_create_station_requires_login(client):
    response = client.post("/api/stations", json=NEW_STATION)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_station_rejects_non_admin(client):
    client.app.dependency_overrides[get_current_user] = lambda: _as_user("USER")
    response = client.post("/api/stations", json=NEW_STATION)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
