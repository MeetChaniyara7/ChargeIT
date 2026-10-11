"""The recommendation service end to end: free chargers for a window, plug filter, OSRM down."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.core.errors import AppError
from app.features.recommendations import service
from app.features.recommendations.osrm import Travel, TravelTimes
from tests.conftest import needs_db
from tests.factories import HOUR, make_booking, make_charger, make_station

pytestmark = needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
HERE = (23.0225, 72.5714)


class StraightLineOnly(TravelTimes):
    """Pretends OSRM is not there: no network, straight-line estimates only."""

    def __init__(self):
        super().__init__(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))


class FakeRoutes:
    """Returns the same fixed drive time for every station."""

    def __init__(self, minutes=7.0):
        self.minutes = minutes
        self.calls = 0

    def estimate(self, origin, destinations):
        self.calls += 1
        return [Travel(self.minutes + i, 3.0 + i, True) for i, _ in enumerate(destinations)]


def recommend(db, travel=None, **kwargs):
    params = dict(lat=HERE[0], lng=HERE[1], connectors=[], start=NOW, duration_minutes=60, now=NOW, travel=travel or FakeRoutes())
    params.update(kwargs)
    return service.recommend(db, **params)


def names(response):
    return [r.station.name for r in response.results]


def test_recommends_stations_with_free_chargers_and_explains_why(db):
    make_charger(db, make_station(db, "Good", 23.03, 72.58), "CCS2", 60, 18)
    result = recommend(db, connectors=["CCS2"])
    [r] = result.results
    assert r.station.name == "Good" and r.free_compatible == 1 and r.travel_is_routed is True
    assert r.reason == "1 CCS2 charger free · 3.0 km · 60 kW"
    assert result.window_start == NOW and result.window_end == NOW + HOUR
    assert 0 < r.score <= 1


def test_a_charger_booked_during_the_window_is_not_counted(db):
    station = make_station(db, "Partly booked", 23.03, 72.58)
    clash, free = make_charger(db, station, "CCS2"), make_charger(db, station, "CCS2")
    make_booking(db, clash, NOW + timedelta(minutes=30), NOW + 2 * HOUR)  # overlaps the 60-minute window
    [r] = recommend(db, connectors=["CCS2"]).results
    assert r.free_compatible == 1
    assert r.station.charger_free == 1  # for recommendations the counts describe the window, not "right now"


def test_a_booking_after_the_window_does_not_matter(db):
    station = make_station(db, "Later booking", 23.03, 72.58)
    charger = make_charger(db, station, "CCS2")
    make_booking(db, charger, NOW + HOUR, NOW + 2 * HOUR)  # starts exactly when the window ends
    assert recommend(db, connectors=["CCS2"]).results[0].free_compatible == 1


def test_stations_with_no_free_compatible_charger_are_left_out(db):
    full = make_station(db, "Fully booked", 23.03, 72.58)
    make_booking(db, make_charger(db, full, "CCS2"), NOW, NOW + 2 * HOUR)
    make_charger(db, make_station(db, "Wrong plug", 23.04, 72.58), "TYPE2")
    make_charger(db, make_station(db, "Broken", 23.05, 72.58), "CCS2", status="OUT_OF_SERVICE")
    assert recommend(db, connectors=["CCS2"]).results == []


def test_expired_holds_do_not_block(db):
    station = make_station(db, "Hold ran out", 23.03, 72.58)
    charger = make_charger(db, station, "CCS2")
    make_booking(db, charger, NOW, NOW + HOUR, status="HELD", hold_expires_at=NOW - timedelta(minutes=1))
    assert names(recommend(db, connectors=["CCS2"])) == ["Hold ran out"]


def test_without_a_plug_filter_any_charger_counts(db):
    make_charger(db, make_station(db, "Type 2 only", 23.03, 72.58), "TYPE2", 22)
    [r] = recommend(db).results
    assert r.reason == "1 charger free · 3.0 km · 22 kW"  # no plug named when none was asked for


def test_stations_beyond_15_km_and_two_wheeler_stations_are_ignored(db):
    make_charger(db, make_station(db, "Too far", 23.40, 72.57))
    make_charger(db, make_station(db, "Scooters", 23.03, 72.58, category="TWO_WHEELER"))
    assert recommend(db).results == []


def test_better_stations_come_first_and_at_most_five_are_returned(db):
    for i in range(7):
        make_charger(db, make_station(db, f"S{i}", 23.03 + i * 0.01, 72.58), "CCS2", 30 + i * 10, 25 - i)
    result = recommend(db, connectors=["CCS2"])
    assert len(result.results) == 5
    scores = [r.score for r in result.results]
    assert scores == sorted(scores, reverse=True)


def test_osrm_is_asked_once_for_all_stations(db):
    for i in range(4):
        make_charger(db, make_station(db, f"S{i}", 23.03 + i * 0.01, 72.58))
    routes = FakeRoutes()
    recommend(db, travel=routes)
    assert routes.calls == 1


def test_still_works_when_osrm_is_down(db):
    make_charger(db, make_station(db, "Near", 23.03, 72.58), "CCS2", 60, 18)
    make_charger(db, make_station(db, "Farther", 23.10, 72.60), "CCS2", 60, 18)
    result = recommend(db, travel=StraightLineOnly(), connectors=["CCS2"])
    assert names(result) == ["Near", "Farther"]
    assert all(r.travel_is_routed is False for r in result.results)  # honest: these are estimates
    assert all(r.travel_minutes > 0 for r in result.results)


def test_an_empty_area_gives_an_empty_list_not_an_error(db):
    assert recommend(db).results == []


@pytest.mark.parametrize("duration", [0, 15, 45, 300])
def test_bad_durations_are_rejected(db, duration):
    with pytest.raises(AppError) as exc:
        recommend(db, duration_minutes=duration)
    assert exc.value.code == "INVALID_DURATION"


def test_start_in_the_past_means_now_and_too_far_ahead_is_rejected(db):
    make_charger(db, make_station(db, "S", 23.03, 72.58))
    assert recommend(db, start=NOW - 5 * HOUR).window_start == NOW
    with pytest.raises(AppError) as exc:
        recommend(db, start=NOW + timedelta(days=9))
    assert exc.value.code == "START_TOO_FAR"


def test_http_endpoint(db_client, db, monkeypatch):
    make_charger(db, make_station(db, "Near", 23.03, 72.58), "CCS2", 60, 18)
    monkeypatch.setattr(service, "travel_times", FakeRoutes())  # no real network in tests
    body = db_client.get("/api/recommendations", params={"lat": HERE[0], "lng": HERE[1], "connector": "CCS2"}).json()
    assert [r["station"]["name"] for r in body["results"]] == ["Near"]
    assert set(body["results"][0]) >= {"score", "reason", "free_compatible", "travel_minutes", "travel_is_routed", "distance_km"}
    assert db_client.get("/api/recommendations", params={"lat": 23, "lng": 72, "duration": 45}).json()["error"]["code"] == "INVALID_DURATION"
    assert db_client.get("/api/recommendations", params={"lat": 23}).status_code == 422
