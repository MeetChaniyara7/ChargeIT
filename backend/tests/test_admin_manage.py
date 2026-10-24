"""Managing people and money from the admin pages: roles, operators, payments, kiosk keys, the activity log (needs the test database)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.features.admin import manage
from app.features.admin import schemas_manage as m
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.kiosk import admin_router, keys
from app.main import app
from tests import factories
from tests.conftest import needs_db

pytestmark = needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


def _committed(make):
    def wrapper(db, *args, **kwargs):
        result = make(db, *args, **kwargs)
        db.commit()
        return result

    return wrapper


make_station = _committed(factories.make_station)
make_charger = _committed(factories.make_charger)
make_user = _committed(factories.make_user)
make_booking = _committed(factories.make_booking)


def set_role(db, user_id, role):
    db.execute(text("UPDATE users SET role = :r WHERE user_id = :u"), {"r": role, "u": user_id})
    db.commit()


def user_obj(db, user_id):
    return db.get(User, user_id)


@pytest.fixture
def world(db):
    station = make_station(db, "Manage hub", 23.03, 72.55)
    admin, other, third = make_user(db), make_user(db), make_user(db)
    set_role(db, admin, "ADMIN")
    return {"station": station, "charger": make_charger(db, station, "CCS2", 60, 20, label="A"), "admin": admin, "other": other, "third": third}


# ================================================================ roles

def test_an_admin_can_make_another_account_an_admin_and_back(db, world):
    admin = user_obj(db, world["admin"])
    user, before = manage.change_role(db, admin, world["other"], "ADMIN")
    assert (before, user.role) == ("USER", "ADMIN")
    user, before = manage.change_role(db, admin, world["other"], "USER")
    assert (before, user.role) == ("ADMIN", "USER")


def test_setting_the_role_it_already_has_changes_nothing(db, world):
    user, before = manage.change_role(db, user_obj(db, world["admin"]), world["other"], "USER")
    assert (before, user.role) == ("USER", "USER")


def test_nobody_can_change_their_own_role(db, world):
    with pytest.raises(AppError) as error:
        manage.change_role(db, user_obj(db, world["admin"]), world["admin"], "USER")
    assert (error.value.status_code, error.value.code) == (409, "CANNOT_CHANGE_OWN_ROLE")
    assert user_obj(db, world["admin"]).role == "ADMIN"


def test_the_last_admin_can_never_be_removed(db, world):
    # Through the API an admin is always acting, so the last admin can only be removed by someone else: the rule is a second guard.
    assert manage._count_admins(db) == 1
    with pytest.raises(AppError) as error:
        manage.change_role(db, user_obj(db, world["other"]), world["admin"], "USER")
    assert (error.value.status_code, error.value.code) == (409, "LAST_ADMIN")
    assert user_obj(db, world["admin"]).role == "ADMIN"
    set_role(db, world["third"], "ADMIN")  # with a second admin the first can be removed by the second
    manage.change_role(db, user_obj(db, world["third"]), world["admin"], "USER")
    assert manage._count_admins(db) == 1


def test_an_unknown_account_is_a_404(db, world):
    with pytest.raises(AppError) as error:
        manage.change_role(db, user_obj(db, world["admin"]), "00000000-0000-0000-0000-000000000000", "ADMIN")
    assert (error.value.status_code, error.value.code) == (404, "USER_NOT_FOUND")


def test_the_user_list_searches_filters_and_counts(db, world):
    make_booking(db, world["charger"], NOW + 2 * H, NOW + 3 * H, user_id=world["other"])
    db.execute(text("UPDATE users SET email = 'findme-driver@test.dev', full_name = 'Find Me' WHERE user_id = :u"), {"u": world["other"]})
    db.commit()
    everyone = manage.list_users(db, None, None, 1, 100, world["admin"])
    assert everyone.total >= 3 and everyone.admins == 1
    assert everyone.items[0].role == "ADMIN" and everyone.items[0].is_you is True  # admins first, and "you" is marked
    found = manage.list_users(db, "findme", None, 1, 20, world["admin"])
    assert [(u.email, u.bookings, u.sign_in, u.is_you) for u in found.items] == [("findme-driver@test.dev", 1, "PASSWORD", False)]
    assert [u.full_name for u in manage.list_users(db, "find me", None, 1, 20, world["admin"]).items] == ["Find Me"]
    assert {u.role for u in manage.list_users(db, None, "ADMIN", 1, 100, world["admin"]).items} == {"ADMIN"}
    assert manage.list_users(db, "%'; DROP TABLE users; --", None, 1, 20, world["admin"]).items == []


# ================================================================ operators

def test_operators_can_be_added_renamed_and_deleted(db, world):
    created = manage.create_operator(db, m.OperatorIn(name="  New Power ", website="https://example.com"))
    assert (created.name, created.website, created.station_count) == ("New Power", "https://example.com", 0)
    with pytest.raises(AppError) as error:
        manage.create_operator(db, m.OperatorIn(name="New Power"))
    assert error.value.code == "OPERATOR_NAME_TAKEN"
    renamed = manage.update_operator(db, created.operator_id, m.OperatorUpdate(name="Newer Power", website=""))
    assert (renamed.name, renamed.website) == ("Newer Power", None)
    assert manage.delete_operator(db, created.operator_id) == "Newer Power"
    assert all(o.operator_id != created.operator_id for o in manage.list_operators(db))


def test_an_operator_with_stations_cannot_be_deleted(db, world):
    operator = manage.create_operator(db, m.OperatorIn(name="Busy Power"))
    db.execute(text("UPDATE stations SET operator_id = :o WHERE station_id = :s"), {"o": operator.operator_id, "s": world["station"]})
    db.commit()
    assert next(o for o in manage.list_operators(db) if o.operator_id == operator.operator_id).station_count == 1
    with pytest.raises(AppError) as error:
        manage.delete_operator(db, operator.operator_id)
    assert (error.value.status_code, error.value.code, error.value.details) == (409, "OPERATOR_IN_USE", {"stations": 1})


def test_renaming_to_a_taken_name_is_refused(db, world):
    a, b = manage.create_operator(db, m.OperatorIn(name="Alpha")), manage.create_operator(db, m.OperatorIn(name="Beta"))
    with pytest.raises(AppError) as error:
        manage.update_operator(db, b.operator_id, m.OperatorUpdate(name="Alpha"))
    assert error.value.code == "OPERATOR_NAME_TAKEN"
    assert a.name == "Alpha"


# ================================================================ payments

def add_payment(db, booking_id, amount, purpose="BOOKING_FEE", status="CAPTURED", refunded=0):
    session_id = None
    if purpose == "ENERGY":
        session_id = db.execute(
            text(
                "INSERT INTO charging_sessions (booking_id, charger_id, source, started_at, ended_at, bill_amount, bill_status) "
                "SELECT booking_id, charger_id, 'BOOKING', :at, :at, :a, 'PAID' FROM bookings WHERE booking_id = :b RETURNING session_id"
            ),
            {"b": booking_id, "at": NOW, "a": amount},
        ).scalar_one()
    db.execute(
        text("INSERT INTO payments (booking_id, session_id, purpose, provider_order_id, amount, status, refunded_amount) VALUES (:b, :sid, :p, :o, :a, :s, :r)"),
        {"b": booking_id, "sid": session_id, "p": purpose, "o": f"order_{booking_id}_{purpose}", "a": amount, "s": status, "r": refunded},
    )
    db.commit()


def test_the_payment_list_filters_and_totals(db, world):
    booking = make_booking(db, world["charger"], NOW + 2 * H, NOW + 3 * H, user_id=world["other"])
    add_payment(db, booking, 199, "BOOKING_FEE", "PARTIALLY_REFUNDED", refunded=50)
    add_payment(db, booking, 300, "ENERGY")
    everything = manage.list_payments(db, None, None, 1, 20)
    assert (everything.total, everything.amount_total, everything.refunded_total) == (2, 499.0, 50.0)
    fees = manage.list_payments(db, "BOOKING_FEE", None, 1, 20)
    assert [(p.purpose, p.amount, p.refunded_amount, p.station_name) for p in fees.items] == [("BOOKING_FEE", 199.0, 50.0, "Manage hub")]
    assert fees.items[0].user_email.endswith("@test.dev")
    assert manage.list_payments(db, None, "CAPTURED", 1, 20).total == 1
    assert manage.list_payments(db, None, None, 2, 1).items[0].payment_id != manage.list_payments(db, None, None, 1, 1).items[0].payment_id


# ================================================================ kiosk keys

def test_rotating_a_key_replaces_it_at_once(db, world):
    device, old_key = admin_router.create_device(db, world["station"], "Door kiosk")
    new, new_key, old = manage.rotate_device(db, device.device_id)
    assert (new.station_id, new.name, new.is_active) == (world["station"], "Door kiosk", True)
    assert old.is_active is False and old.device_id == device.device_id
    assert new_key != old_key and keys.matches(new_key, new.api_key_hash) and not keys.matches(old_key, new.api_key_hash)
    with pytest.raises(AppError) as error:  # a revoked key cannot be rotated again
        manage.rotate_device(db, device.device_id)
    assert error.value.code == "DEVICE_REVOKED"


def test_renaming_a_kiosk(db, world):
    device, _ = admin_router.create_device(db, world["station"], "Old name")
    assert manage.rename_device(db, device.device_id, "  Entrance  ").name == "Entrance"
    with pytest.raises(AppError) as error:
        manage.rename_device(db, "00000000-0000-0000-0000-000000000000", "x")
    assert error.value.code == "DEVICE_NOT_FOUND"


# ================================================================ over HTTP, with the activity log

def as_user(user_id, role="USER", email="x@test.dev"):
    app.dependency_overrides[get_current_user] = lambda: User(user_id=user_id, email=email, role=role)


NEW_ROUTES = [
    ("get", "/api/admin/users"), ("patch", "/api/admin/users/{other}/role"), ("get", "/api/admin/payments"), ("get", "/api/admin/activity"),
    ("get", "/api/admin/operators"), ("post", "/api/admin/operators"), ("patch", "/api/admin/operators/{other}"), ("delete", "/api/admin/operators/{other}"),
    ("patch", "/api/admin/devices/{other}"), ("post", "/api/admin/devices/{other}/rotate"),
]


@pytest.mark.parametrize("method,path", NEW_ROUTES)
def test_http_the_new_admin_routes_need_the_admin_role(db_client, world, method, path):
    path = path.format(**{k: str(v) for k, v in world.items()})
    as_user(world["other"], "USER")
    assert db_client.request(method.upper(), path, json={}).status_code == 403
    app.dependency_overrides.pop(get_current_user)
    assert db_client.request(method.upper(), path, json={}).status_code == 401


def test_http_role_change_and_the_activity_log(db_client, db, world):
    as_user(world["admin"], "ADMIN", "boss@test.dev")
    done = db_client.patch(f"/api/admin/users/{world['other']}/role", json={"role": "ADMIN"})
    assert done.status_code == 200 and done.json()["role"] == "ADMIN"
    own = db_client.patch(f"/api/admin/users/{world['admin']}/role", json={"role": "USER"})
    assert (own.status_code, own.json()["error"]["code"]) == (409, "CANNOT_CHANGE_OWN_ROLE")
    assert db_client.patch(f"/api/admin/users/{world['other']}/role", json={"role": "OWNER"}).status_code == 422
    log = db_client.get("/api/admin/activity").json()
    assert log["total"] == 1
    entry = log["items"][0]
    assert (entry["admin_email"], entry["action"], entry["target"], entry["details"]) == ("boss@test.dev", "USER_ROLE_CHANGED", db.get(User, world["other"]).email, {"from": "USER", "to": "ADMIN"})


def test_http_the_kiosk_key_actions_are_logged(db_client, db, world):
    as_user(world["admin"], "ADMIN", "boss@test.dev")
    created = db_client.post(f"/api/admin/stations/{world['station']}/devices", json={"name": "Door"}).json()
    rotated = db_client.post(f"/api/admin/devices/{created['device_id']}/rotate").json()
    assert rotated["key"].startswith("ks_") and rotated["key"] != created["key"] and rotated["device_id"] != created["device_id"]
    assert db_client.patch(f"/api/admin/devices/{rotated['device_id']}", json={"name": "Entrance"}).json()["name"] == "Entrance"
    assert db_client.post(f"/api/admin/devices/{rotated['device_id']}/disable").json()["is_active"] is False
    actions = [a["action"] for a in db_client.get("/api/admin/activity").json()["items"]]
    assert actions == ["KIOSK_KEY_REVOKED", "KIOSK_RENAMED", "KIOSK_KEY_ROTATED", "KIOSK_KEY_CREATED"]
    assert db_client.get("/api/kiosk/status", headers={"X-Device-Key": created["key"]}).status_code == 403  # the rotated-out key is dead


def test_http_charger_changes_are_logged_with_who_did_them(db_client, db, world):
    as_user(world["admin"], "ADMIN", "boss@test.dev")
    db_client.post(f"/api/admin/chargers/{world['charger']}/out-of-service", json={})
    db_client.post(f"/api/admin/chargers/{world['charger']}/restore")
    db_client.patch(f"/api/admin/stations/{world['station']}", json={"city": "Surat"})
    items = db_client.get("/api/admin/activity").json()["items"]
    assert [i["action"] for i in items] == ["STATION_EDITED", "CHARGER_RESTORED", "CHARGER_OUT_OF_SERVICE"]
    assert items[2]["target"] == "Manage hub / A" and all(i["admin_email"] == "boss@test.dev" for i in items)


def test_http_operators_users_and_payments_lists(db_client, db, world):
    as_user(world["admin"], "ADMIN", "boss@test.dev")
    created = db_client.post("/api/admin/operators", json={"name": "HTTP Power", "website": "https://h.example"})
    assert created.status_code == 201
    oid = created.json()["operator_id"]
    assert db_client.post("/api/admin/operators", json={"name": "HTTP Power"}).json()["error"]["code"] == "OPERATOR_NAME_TAKEN"
    assert db_client.post("/api/admin/operators", json={"name": ""}).status_code == 422
    assert db_client.patch(f"/api/admin/operators/{oid}", json={"name": "HTTP Power 2"}).json()["name"] == "HTTP Power 2"
    assert db_client.delete(f"/api/admin/operators/{oid}").status_code == 204
    assert db_client.delete(f"/api/admin/operators/{oid}").status_code == 404
    users = db_client.get("/api/admin/users?q=@test.dev&role=ADMIN").json()
    assert users["admins"] == 1 and users["items"][0]["is_you"] is True
    assert db_client.get("/api/admin/users?role=OWNER").status_code == 422
    assert db_client.get("/api/admin/payments?purpose=ENERGY").json()["total"] == 0
    assert db_client.get("/api/admin/payments?status=BOGUS").status_code == 422
