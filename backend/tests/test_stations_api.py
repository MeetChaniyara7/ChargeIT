"""Station search: map area, radius, plug filter, live free counts (needs the test database)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text

from app.features.stations import service
from app.features.stations.repository import StationQuery
from app.features.stations.service import SearchFilters
from tests.conftest import needs_db
from tests.factories import HOUR, make_booking, make_charger, make_station

pytestmark = needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)  # 15:30 IST on a Monday
AHMEDABAD = (23.0225, 72.5714)


def search(db, **kwargs):
    open_now = kwargs.pop("open_now", False)
    return service.search(db, SearchFilters(StationQuery(**kwargs), open_now=open_now), NOW)


def names(response):
    return [s.name for s in response.stations]


def test_bbox_returns_only_stations_inside_the_map_area(db):
    make_charger(db, make_station(db, "Inside", 23.03, 72.55))
    make_charger(db, make_station(db, "Far north", 24.50, 72.55))
    make_charger(db, make_station(db, "Far east", 23.03, 74.20))
    assert names(search(db, bbox=(72.4, 22.9, 72.7, 23.2))) == ["Inside"]


def test_radius_search_sorts_by_distance_and_reports_it(db):
    make_charger(db, make_station(db, "Far", 23.15, 72.57))      # ~14 km
    make_charger(db, make_station(db, "Near", 23.03, 72.58))     # ~1 km
    make_charger(db, make_station(db, "Middle", 23.08, 72.57))   # ~6 km
    make_charger(db, make_station(db, "Too far", 23.40, 72.57))  # ~42 km
    result = search(db, center=AHMEDABAD, radius_km=15)
    assert names(result) == ["Near", "Middle", "Far"]
    distances = [s.distance_km for s in result.stations]
    assert distances == sorted(distances) and 0.5 < distances[0] < 2
    assert all(s.eta_minutes_estimate and s.eta_minutes_estimate >= 1 for s in result.stations)


def test_without_a_search_point_there_is_no_distance(db):
    make_charger(db, make_station(db, "A"))
    [station] = search(db).stations
    assert station.distance_km is None and station.eta_minutes_estimate is None


def test_connector_filter_matches_any_plug_and_counts_only_matching_chargers(db):
    both = make_station(db, "Both plugs")
    make_charger(db, both, "CCS2", 60)
    make_charger(db, both, "CCS2", 30)
    make_charger(db, both, "TYPE2", 22)
    make_charger(db, make_station(db, "Only Type 2"), "TYPE2", 7)
    make_charger(db, make_station(db, "CHAdeMO"), "CHADEMO", 50)

    ccs = search(db, connectors=["CCS2"])
    assert names(ccs) == ["Both plugs"]
    assert ccs.stations[0].charger_total == 2 and ccs.stations[0].connector_types == ["CCS2"]  # the Type 2 charger is not counted

    assert names(search(db, connectors=["CCS2", "CHADEMO"])) == ["Both plugs", "CHAdeMO"]
    assert search(db, connectors=["TYPE1"]).stations == []


def test_min_power_filter(db):
    station = make_station(db, "Mixed speeds")
    make_charger(db, station, "CCS2", 22)
    make_charger(db, station, "CCS2", 60)
    make_charger(db, make_station(db, "Slow only"), "TYPE2", 7)
    result = search(db, min_power_kw=50)
    assert names(result) == ["Mixed speeds"]
    assert result.stations[0].charger_total == 1 and result.stations[0].min_power_kw == 60


def test_two_wheeler_and_inactive_stations_are_not_shown(db):
    make_charger(db, make_station(db, "Car station"))
    make_charger(db, make_station(db, "Scooter station", category="TWO_WHEELER"))
    make_charger(db, make_station(db, "Closed down", active=False))
    assert names(search(db)) == ["Car station"]


def test_limit_and_truncated_flag(db):
    for i in range(5):
        make_charger(db, make_station(db, f"S{i}"))
    result = search(db, limit=3)
    assert result.count == 3 and result.truncated is True
    assert search(db, limit=5).truncated is False


def test_free_count_reflects_bookings_right_now(db):
    station = make_station(db, "Busy one")
    free, booked, held, expired_hold, broken = (make_charger(db, station) for _ in range(5))
    db.execute(text("UPDATE chargers SET status = 'OUT_OF_SERVICE' WHERE charger_id = :c"), {"c": broken})
    make_booking(db, booked, NOW - HOUR, NOW + HOUR)                                              # confirmed, covers now
    make_booking(db, held, NOW, NOW + HOUR, status="HELD", hold_expires_at=NOW + timedelta(minutes=3))   # someone is paying
    make_booking(db, expired_hold, NOW, NOW + HOUR, status="HELD", hold_expires_at=NOW - timedelta(minutes=1))  # ran out: free again
    make_booking(db, free, NOW + 2 * HOUR, NOW + 3 * HOUR)                                        # later today: not busy now
    [s] = search(db).stations
    # Free now: the charger booked LATER today and the one whose hold ran out.
    # Not free: the confirmed booking, the live hold, and the broken charger.
    assert (s.charger_total, s.charger_free) == (5, 2)


def test_estimated_data_and_rating_are_flagged(db):
    make_charger(db, make_station(db, "Generated", rating=4.5, estimated=["rating"]), estimated=["price_per_kwh"])
    make_charger(db, make_station(db, "Real", rating=4.0))
    by_name = {s.name: s for s in search(db).stations}
    assert by_name["Generated"].has_estimated_data and by_name["Generated"].rating_is_estimated
    assert not by_name["Real"].has_estimated_data and not by_name["Real"].rating_is_estimated


def test_open_now_hides_only_stations_known_to_be_closed(db):
    make_charger(db, make_station(db, "Always open", opening_hours="24/7"))
    make_charger(db, make_station(db, "Closed at night", opening_hours="Mo-Su 18:00-23:00"))  # it is 15:30 IST
    make_charger(db, make_station(db, "Hours unknown"))
    assert names(search(db, open_now=True)) == ["Always open", "Hours unknown"]
    by_name = {s.name: s.is_open_now for s in search(db).stations}
    assert by_name == {"Always open": True, "Closed at night": False, "Hours unknown": None}


def test_operator_name_is_returned(db):
    make_charger(db, make_station(db, "Tata one", operator="Tata Power"))
    assert search(db).stations[0].operator_name == "Tata Power"


def test_number_of_database_queries_does_not_grow_with_the_number_of_stations(db):
    def count_queries(station_count: int) -> int:
        for i in range(station_count):
            make_charger(db, make_station(db, f"S{station_count}-{i}"))
        statements = []
        engine = db.get_bind().engine if hasattr(db.get_bind(), "engine") else db.get_bind()

        def record(conn, cursor, statement, *args):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            search(db, limit=500)
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(statements)

    few = count_queries(2)
    many = count_queries(40)
    assert many == few  # stations, then chargers, then bookings: always the same three steps


# ---- over HTTP ----

def test_http_search_validation(db_client):
    assert db_client.get("/api/stations", params={"bbox": "1,2,3"}).json()["error"]["code"] == "INVALID_BBOX"
    assert db_client.get("/api/stations", params={"bbox": "73,23,72,24"}).json()["error"]["code"] == "INVALID_BBOX"
    assert db_client.get("/api/stations", params={"lat": 23}).json()["error"]["code"] == "INVALID_LOCATION"
    assert db_client.get("/api/stations", params={"connector": "TESLA"}).status_code == 422
    assert db_client.get("/api/stations", params={"limit": 0}).status_code == 422


def test_http_lat_lng_alone_means_within_the_default_radius(db_client, db):
    make_charger(db, make_station(db, "Near", 23.03, 72.58))
    make_charger(db, make_station(db, "Beyond 15 km", 23.30, 72.58))
    body = db_client.get("/api/stations", params={"lat": AHMEDABAD[0], "lng": AHMEDABAD[1]}).json()
    assert [s["name"] for s in body["stations"]] == ["Near"]


def test_http_count_and_detail(db_client, db):
    station = make_station(db, "Detail me", opening_hours="24/7")
    make_charger(db, station, "CCS2", 60, 18)
    assert db_client.get("/api/stations/count").json() == {"count": 1}
    detail = db_client.get(f"/api/stations/{station}").json()
    assert detail["name"] == "Detail me" and detail["is_open_now"] is True
    [charger] = detail["chargers"]
    assert charger["connector_type"] == "CCS2" and charger["power_kw"] == 60 and charger["price_per_kwh"] == 18
    assert charger["free_now"] is True and charger["is_estimated"] is False


def test_http_unknown_station_is_404(db_client):
    response = db_client.get("/api/stations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404 and response.json()["error"]["code"] == "STATION_NOT_FOUND"
    assert db_client.get("/api/stations/not-a-uuid").status_code == 422


@pytest.mark.parametrize("path", ["/api/recommendations?lat=23&lng=72", "/api/geocode?q=bopal"])
def test_recommendations_and_geocoding_need_a_login(client, path):
    assert client.get(path).status_code == 401
