"""Search suggestions (stations, operators, cities) and the operator / price station filters."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from app.features.search import repository, service
from app.features.search.repository import Area, Match
from app.features.stations import service as station_service
from app.features.stations.repository import StationQuery
from app.features.stations.service import SearchFilters
from tests.conftest import needs_db
from tests.factories import make_charger, make_station

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
AHMEDABAD = (23.0225, 72.5714)


def _area(name: str) -> Area:
    return Area(name, 1, 23.0, 23.0, 72.5, 72.5)


# ---- pure helpers (no database) ----

def test_normalize_trims_and_collapses_spaces():
    assert service.normalize("  tata   power ") == "tata power"


def test_did_you_mean_only_when_nothing_contains_the_text():
    close = [Match(_area("Tata Power"), 0.8)]
    assert service.did_you_mean(close, []) == "Tata Power"
    exact = [Match(_area("Bopal"), 1.0)]
    assert service.did_you_mean(close, exact) is None  # something really matched
    assert service.did_you_mean([Match(_area("Far off"), 0.3)]) is None  # not similar enough
    assert service.did_you_mean([], []) is None


def test_did_you_mean_picks_the_most_similar():
    assert service.did_you_mean([Match(_area("A"), 0.6)], [Match(_area("B"), 0.75)]) == "B"


def test_escape_like_keeps_wildcards_literal():
    assert repository._escape_like("50%_off\\") == "50\\%\\_off\\\\"


# ---- with the test database ----

def suggest(db, text, origin=None):
    return service.suggest(db, text, NOW, origin)


@needs_db
def test_exact_and_prefix_station_matches_rank_first(db):
    make_charger(db, make_station(db, "Bopal Fast Hub"))
    make_charger(db, make_station(db, "South Bopal Plaza"))
    make_charger(db, make_station(db, "Navrangpura Mall"))
    result = suggest(db, "bopal")
    assert [s.name for s in result.stations] == ["Bopal Fast Hub", "South Bopal Plaza"]
    assert result.did_you_mean is None


@needs_db
def test_station_rows_carry_live_free_counts(db):
    station = make_station(db, "Counted")
    make_charger(db, station)
    make_charger(db, station, status="OUT_OF_SERVICE")
    [row] = suggest(db, "counted").stations
    assert (row.charger_total, row.charger_free) == (2, 1)


@needs_db
def test_typo_finds_operator_and_suggests_the_spelling(db):
    for i in range(3):
        make_charger(db, make_station(db, f"EZ Charge {i}", operator="Tata Power"))
    make_charger(db, make_station(db, "Other", operator="Jio-bp"))
    result = suggest(db, "tata powr")
    assert [(o.name, o.station_count) for o in result.operators] == [("Tata Power", 3)]
    assert result.did_you_mean == "Tata Power"


@needs_db
def test_operator_counts_ignore_hidden_stations(db):
    make_charger(db, make_station(db, "Car", operator="Ather Grid"))
    make_charger(db, make_station(db, "Scooter", operator="Ather Grid", category="TWO_WHEELER"))
    make_charger(db, make_station(db, "Gone", operator="Ather Grid", active=False))
    [operator] = suggest(db, "ather").operators
    assert operator.station_count == 1


@needs_db
def test_the_brand_chips_list_busiest_brands_first_and_skip_hidden_stations(db):
    for i in range(2):
        make_charger(db, make_station(db, f"Tata {i}", operator="Zz Brand A"))
    make_charger(db, make_station(db, "One", operator="Zz Brand B"))
    make_charger(db, make_station(db, "Gone", operator="Zz Brand C", active=False))
    make_charger(db, make_station(db, "Scooter", operator="Zz Brand D", category="TWO_WHEELER"))
    ours = [(n, c) for n, c in repository.top_operators(db, 50) if n.startswith("Zz Brand")]
    assert ours == [("Zz Brand A", 2), ("Zz Brand B", 1)]


@needs_db
def test_two_wheeler_stations_are_never_suggested(db):
    make_charger(db, make_station(db, "Scooter Point", category="TWO_WHEELER"))
    assert suggest(db, "scooter").stations == []


@needs_db
def test_cities_come_with_counts_and_an_area(db):
    from sqlalchemy import text

    a = make_station(db, "One", 23.00, 72.50)
    b = make_station(db, "Two", 23.10, 72.60)
    db.execute(text("UPDATE stations SET city = 'Gandhinagar' WHERE station_id IN (:a, :b)"), {"a": a, "b": b})
    [city] = suggest(db, "gandhi").cities
    assert (city.name, city.station_count) == ("Gandhinagar", 2)
    assert city.bbox == [23.00, 23.10, 72.50, 72.60]  # south, north, west, east
    assert city.latitude == pytest.approx(23.05) and city.longitude == pytest.approx(72.55)


@needs_db
def test_address_matches_rank_after_name_matches(db):
    from sqlalchemy import text

    by_address = make_station(db, "Shell Petrol Pump")
    db.execute(text("UPDATE stations SET address = 'SP Ring Road, Bopal' WHERE station_id = :s"), {"s": by_address})
    make_charger(db, by_address)
    make_charger(db, make_station(db, "Bopal Hub"))
    result = suggest(db, "bopal")
    assert [s.name for s in result.stations] == ["Bopal Hub", "Shell Petrol Pump"]
    assert result.did_you_mean is None


@needs_db
def test_city_names_with_stray_spaces_count_as_one(db):
    from sqlalchemy import text

    a, b = make_station(db, "One"), make_station(db, "Two")
    db.execute(text("UPDATE stations SET city = 'Ahmedabad' WHERE station_id = :s"), {"s": a})
    db.execute(text("UPDATE stations SET city = 'Ahmedabad ' WHERE station_id = :s"), {"s": b})
    assert [(c.name, c.station_count) for c in suggest(db, "ahmed").cities] == [("Ahmedabad", 2)]


@needs_db
def test_did_you_mean_prefers_the_operator_to_its_station_names(db):
    make_charger(db, make_station(db, "Tata Power – Shell Petrol Pump", operator="Tata Power"))
    assert suggest(db, "tata powr").did_you_mean == "Tata Power"


@needs_db
def test_nothing_similar_returns_empty_sections(db):
    make_charger(db, make_station(db, "Bopal Hub"))
    result = suggest(db, "zzqx")
    assert (result.stations, result.operators, result.cities, result.did_you_mean) == ([], [], [], None)


@needs_db
def test_equal_matches_are_ordered_by_distance(db):
    make_charger(db, make_station(db, "Jio-bp Far", 23.30, 72.57))
    make_charger(db, make_station(db, "Jio-bp Near", 23.03, 72.58))
    assert [s.name for s in suggest(db, "jio-bp", AHMEDABAD).stations] == ["Jio-bp Near", "Jio-bp Far"]
    assert suggest(db, "jio-bp", AHMEDABAD).stations[0].distance_km is not None


@needs_db
def test_wildcards_in_the_text_are_not_wildcards(db):
    make_charger(db, make_station(db, "Anything"))
    assert suggest(db, "%%").stations == []


@needs_db
def test_number_of_queries_does_not_grow_with_matches(db):
    def count_queries(n: int) -> int:
        for i in range(n):
            make_charger(db, make_station(db, f"Hub {n}-{i}", operator=f"Op {i % 3}"))
        statements = []
        engine = db.get_bind().engine if hasattr(db.get_bind(), "engine") else db.get_bind()

        def record(conn, cursor, statement, *args):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            suggest(db, "hub")
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(statements)

    # stations, their chargers, operators, cities, bookings: the same five steps every time
    assert count_queries(2) == count_queries(12) == 5


# ---- station search filters added for smart search ----

def _search(db, **kwargs):
    return [s.name for s in station_service.search(db, SearchFilters(StationQuery(**kwargs)), NOW).stations]


@needs_db
def test_operator_filter_ignores_capitalisation(db):
    make_charger(db, make_station(db, "Tata one", operator="Tata Power"))
    make_charger(db, make_station(db, "Jio one", operator="Jio-bp"))
    assert _search(db, operator="tata power") == ["Tata one"]
    assert _search(db, operator="Nobody") == []


@needs_db
def test_max_price_filter_counts_only_cheap_enough_chargers(db):
    mixed = make_station(db, "Mixed prices")
    make_charger(db, mixed, price=12)
    make_charger(db, mixed, price=24)
    make_charger(db, make_station(db, "Pricey"), price=25)
    make_charger(db, make_station(db, "Price unknown"), price=None)
    result = station_service.search(db, SearchFilters(StationQuery(max_price_per_kwh=15)), NOW)
    assert [s.name for s in result.stations] == ["Mixed prices"]
    assert result.stations[0].charger_total == 1 and result.stations[0].min_price_per_kwh == 12


# ---- over HTTP ----

@needs_db
def test_http_suggest(db_client, db):
    make_charger(db, make_station(db, "Bopal Hub"))
    body = db_client.get("/api/search/suggest", params={"q": "  bopal  "}).json()
    assert body["query"] == "bopal" and [s["name"] for s in body["stations"]] == ["Bopal Hub"]


@needs_db
def test_http_suggest_validation(db_client):
    assert db_client.get("/api/search/suggest", params={"q": " a "}).json()["error"]["code"] == "QUERY_TOO_SHORT"
    assert db_client.get("/api/search/suggest", params={"q": "x" * 81}).status_code == 422
    assert db_client.get("/api/search/suggest").status_code == 422
    assert db_client.get("/api/search/suggest", params={"q": "bopal", "lat": 23}).json()["error"]["code"] == "INVALID_LOCATION"


@needs_db
def test_http_station_filters(db_client, db):
    make_charger(db, make_station(db, "Tata cheap", operator="Tata Power"), price=12)
    make_charger(db, make_station(db, "Tata dear", operator="Tata Power"), price=22)
    body = db_client.get("/api/stations", params={"operator": "TATA POWER", "max_price": 15}).json()
    assert [s["name"] for s in body["stations"]] == ["Tata cheap"]
    assert db_client.get("/api/stations", params={"max_price": 0}).status_code == 422


def test_suggest_needs_a_login(client):
    assert client.get("/api/search/suggest", params={"q": "bopal"}).status_code == 401
