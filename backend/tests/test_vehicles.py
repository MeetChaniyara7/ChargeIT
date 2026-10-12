"""/api/me/vehicles: list, add, change, delete, one default per user (needs the test database)."""

import pytest

from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.main import app
from tests.conftest import needs_db
from tests.factories import make_user

pytestmark = needs_db


@pytest.fixture
def api(db_client, db):
    users = {"me": make_user(db), "you": make_user(db)}
    db.commit()

    def sign_in(name):
        app.dependency_overrides[get_current_user] = lambda: User(user_id=users[name], email=f"{name}@test.dev", role="USER")

    sign_in("me")
    db_client.sign_in = sign_in
    return db_client


CAR = {"nickname": "Tata Nexon EV", "connector_type": "CCS2", "battery_kwh": 40.5}


def test_the_first_vehicle_becomes_the_default(api):
    created = api.post("/api/me/vehicles", json=CAR)
    assert created.status_code == 201
    body = created.json()
    assert body["is_default"] is True and body["battery_kwh"] == 40.5 and body["connector_type"] == "CCS2"
    assert api.get("/api/me/vehicles").json() == [body]


def test_a_second_vehicle_is_not_the_default_unless_asked(api):
    first = api.post("/api/me/vehicles", json=CAR).json()
    second = api.post("/api/me/vehicles", json={**CAR, "nickname": "Scooter car", "connector_type": "TYPE2"}).json()
    assert (first["is_default"], second["is_default"]) == (True, False)
    third = api.post("/api/me/vehicles", json={**CAR, "nickname": "New default", "is_default": True}).json()
    listed = api.get("/api/me/vehicles").json()
    assert [v["nickname"] for v in listed][0] == "New default"  # the default comes first
    assert [v["is_default"] for v in listed].count(True) == 1 and third["is_default"]


def test_changing_a_vehicle_and_switching_the_default(api):
    first = api.post("/api/me/vehicles", json=CAR).json()
    second = api.post("/api/me/vehicles", json={**CAR, "nickname": "Other"}).json()
    changed = api.patch(f"/api/me/vehicles/{second['vehicle_id']}", json={"nickname": " Renamed ", "battery_kwh": 60, "is_default": True}).json()
    assert changed["nickname"] == "Renamed" and changed["battery_kwh"] == 60 and changed["is_default"] is True
    assert api.get("/api/me/vehicles").json()[1]["vehicle_id"] == first["vehicle_id"]
    assert api.get("/api/me/vehicles").json()[1]["is_default"] is False
    # A change that sends nothing keeps everything.
    assert api.patch(f"/api/me/vehicles/{second['vehicle_id']}", json={}).json()["nickname"] == "Renamed"
    # The default cannot simply be switched off: pick another one instead.
    refused = api.patch(f"/api/me/vehicles/{second['vehicle_id']}", json={"is_default": False})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "DEFAULT_REQUIRED"


def test_deleting_the_default_promotes_another_vehicle(api):
    first = api.post("/api/me/vehicles", json=CAR).json()
    second = api.post("/api/me/vehicles", json={**CAR, "nickname": "Other"}).json()
    assert api.delete(f"/api/me/vehicles/{first['vehicle_id']}").status_code == 204
    [left] = api.get("/api/me/vehicles").json()
    assert left["vehicle_id"] == second["vehicle_id"] and left["is_default"] is True
    assert api.delete(f"/api/me/vehicles/{second['vehicle_id']}").status_code == 204
    assert api.get("/api/me/vehicles").json() == []


def test_people_only_see_and_change_their_own_vehicles(api):
    mine = api.post("/api/me/vehicles", json=CAR).json()
    api.sign_in("you")
    assert api.get("/api/me/vehicles").json() == []
    assert api.patch(f"/api/me/vehicles/{mine['vehicle_id']}", json={"nickname": "Stolen"}).status_code == 404
    assert api.delete(f"/api/me/vehicles/{mine['vehicle_id']}").status_code == 404
    api.sign_in("me")
    assert api.get("/api/me/vehicles").json()[0]["nickname"] == "Tata Nexon EV"


@pytest.mark.parametrize(
    "change",
    [{"nickname": ""}, {"nickname": "x" * 41}, {"connector_type": "TESLA"}, {"battery_kwh": 0}, {"battery_kwh": -5}, {"battery_kwh": 251}, {"battery_kwh": "big"}],
)
def test_invalid_vehicles_are_refused(api, change):
    assert api.post("/api/me/vehicles", json={**CAR, **change}).status_code == 422
    assert api.get("/api/me/vehicles").json() == []


def test_the_number_of_vehicles_is_limited(api):
    for i in range(10):
        assert api.post("/api/me/vehicles", json={**CAR, "nickname": f"Car {i}"}).status_code == 201
    over = api.post("/api/me/vehicles", json=CAR)
    assert over.status_code == 409 and over.json()["error"]["code"] == "TOO_MANY_VEHICLES"


def test_vehicles_need_a_login(client):
    assert client.get("/api/me/vehicles").status_code == 401
    assert client.post("/api/me/vehicles", json=CAR).status_code == 401
