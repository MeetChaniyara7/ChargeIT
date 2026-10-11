"""Drive times: real routing when OSRM works, straight-line estimates when it doesn't."""

import httpx
import pytest

from app.features.recommendations.osrm import RETRY_AFTER_FAILURE_SECONDS, TravelTimes

ORIGIN = (23.0225, 72.5714)
STATIONS = [(23.0300, 72.5800), (23.0900, 72.6000)]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(handler, clock=None):
    calls = []

    def recording(request: httpx.Request):
        calls.append(request)
        return handler(request)

    return TravelTimes(client=httpx.Client(transport=httpx.MockTransport(recording)), clock=clock or Clock()), calls


def ok(durations, distances):
    return lambda request: httpx.Response(200, json={"code": "Ok", "durations": [durations], "distances": [distances]})


def test_uses_real_road_times_from_osrm():
    travel, calls = make(ok([300, 960], [2500, 9100]))
    result = travel.estimate(ORIGIN, STATIONS)
    assert [(t.minutes, t.distance_km, t.routed) for t in result] == [(5.0, 2.5, True), (16.0, 9.1, True)]
    assert len(calls) == 1  # ONE request for all stations
    url = str(calls[0].url)
    assert "72.5714,23.0225;72.58,23.03;72.6,23.09" in url  # longitude first, origin first
    assert "sources=0" in url and "destinations=1%3B2" in url


def test_falls_back_to_straight_line_at_25_kmh_when_osrm_errors():
    travel, _ = make(lambda r: httpx.Response(500))
    result = travel.estimate(ORIGIN, STATIONS)
    assert all(t.routed is False for t in result)
    assert result[0].minutes == pytest.approx(result[0].distance_km / 25 * 60)
    assert 0.5 < result[0].distance_km < 2  # about 1.1 km apart


def test_falls_back_when_osrm_is_unreachable_or_times_out():
    def boom(request):
        raise httpx.ConnectTimeout("too slow")

    travel, _ = make(boom)
    assert [t.routed for t in travel.estimate(ORIGIN, STATIONS)] == [False, False]


@pytest.mark.parametrize("body", [{"code": "InvalidQuery"}, {"code": "Ok"}, {"nonsense": True}])
def test_falls_back_on_unexpected_answers(body):
    travel, _ = make(lambda r: httpx.Response(200, json=body))
    assert [t.routed for t in travel.estimate(ORIGIN, STATIONS)] == [False, False]


def test_a_station_osrm_cannot_reach_keeps_its_own_estimate():
    travel, _ = make(lambda r: httpx.Response(200, json={"code": "Ok", "durations": [[300, None]], "distances": [[2500, None]]}))
    first, second = travel.estimate(ORIGIN, STATIONS)
    assert first.routed is True and second.routed is False


def test_identical_requests_are_answered_from_the_cache():
    travel, calls = make(ok([300, 960], [2500, 9100]))
    first = travel.estimate(ORIGIN, STATIONS)
    second = travel.estimate((ORIGIN[0] + 0.0001, ORIGIN[1]), STATIONS)  # a few metres away: same cache entry
    assert first == second and len(calls) == 1


def test_cache_expires():
    clock = Clock()
    travel, calls = make(ok([300, 960], [2500, 9100]), clock)
    travel.estimate(ORIGIN, STATIONS)
    clock.now += 61  # cache lasts 60 s
    travel.estimate(ORIGIN, STATIONS)
    assert len(calls) == 2


def test_after_a_failure_osrm_is_left_alone_for_a_while_then_tried_again():
    clock = Clock()
    outcomes = iter([httpx.Response(500), httpx.Response(200, json={"code": "Ok", "durations": [[300, 960]], "distances": [[2500, 9100]]})])
    travel, calls = make(lambda r: next(outcomes), clock)

    assert not travel.estimate(ORIGIN, STATIONS)[0].routed
    clock.now += RETRY_AFTER_FAILURE_SECONDS - 1
    assert not travel.estimate((24.0, 73.0), STATIONS)[0].routed   # still resting: no new request
    assert len(calls) == 1
    clock.now += 2
    assert travel.estimate((24.0, 73.0), STATIONS)[0].routed       # rested: asks again and it works
    assert len(calls) == 2


def test_no_destinations_means_no_request():
    travel, calls = make(ok([], []))
    assert travel.estimate(ORIGIN, []) == [] and calls == []
