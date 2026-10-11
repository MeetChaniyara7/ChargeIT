"""Place search: caching, the 1-request-per-second rule and error handling. No real network calls."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.features.geocoding import service
from app.features.geocoding.service import RateLimiter, normalize_query
from tests.conftest import needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)

NOMINATIM_ANSWER = [
    {"display_name": "Bopal, Ahmedabad, Gujarat, India", "lat": "23.0343", "lon": "72.4684", "type": "suburb",
     "boundingbox": ["23.0100", "23.0600", "72.4400", "72.5000"]},
    {"display_name": "Broken entry without coordinates"},
]


def fake_nominatim(answer=None, status=200):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        return httpx.Response(status, json=NOMINATIM_ANSWER if answer is None else answer)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


class NoWait(RateLimiter):
    def __init__(self):
        super().__init__(1.1, 5.0, clock=lambda: 0.0, sleep=lambda s: None)


# ---------- the 1 request/second rule ----------

def test_rate_limiter_makes_each_caller_wait_its_turn():
    now = [100.0]
    slept = []

    def sleep(seconds):
        slept.append(round(seconds, 2))
        now[0] += seconds

    limiter = RateLimiter(1.1, 5.0, clock=lambda: now[0], sleep=sleep)
    limiter.wait_turn()           # first call goes straight through
    limiter.wait_turn()           # second must wait ~1.1 s
    now[0] += 5                   # a quiet spell...
    limiter.wait_turn()           # ...so no waiting again
    assert slept == [1.1]


def test_rate_limiter_says_busy_instead_of_queueing_for_too_long():
    limiter = RateLimiter(1.1, 2.0, clock=lambda: 0.0, sleep=lambda s: None)
    limiter.wait_turn()           # goes straight through
    limiter.wait_turn()           # waits 1.1 s: fine, under the 2 s cap
    with pytest.raises(AppError) as exc:
        limiter.wait_turn()       # would wait 2.2 s: refused
    assert exc.value.status_code == 429 and exc.value.code == "SEARCH_BUSY"


# ---------- small pieces ----------

@pytest.mark.parametrize("raw, expected", [("  Bopal,   AHMEDABAD ", "bopal, ahmedabad"), ("Bopal", "bopal"), ("\tSG\nHighway ", "sg highway")])
def test_normalize_query(raw, expected):
    assert normalize_query(raw) == expected


def test_a_malformed_place_in_the_answer_is_skipped_not_fatal():
    client, _ = fake_nominatim()
    places = service.search_nominatim("bopal", client, limiter=NoWait())
    assert [p.name for p in places] == ["Bopal, Ahmedabad, Gujarat, India"]
    assert places[0].lat == 23.0343 and places[0].bbox == (23.01, 23.06, 72.44, 72.5)


def test_request_follows_nominatim_policy():
    client, calls = fake_nominatim()
    service.search_nominatim("bopal", client, limiter=NoWait())
    request = calls[0]
    assert request.headers["User-Agent"].startswith("ChargeSpot/")      # identifies the app
    params = dict(request.url.params)
    assert params["countrycodes"] == "in" and params["q"] == "bopal" and params["format"] == "jsonv2"


@pytest.mark.parametrize("failure", [lambda r: httpx.Response(503), lambda r: (_ for _ in ()).throw(httpx.ConnectError("down"))])
def test_nominatim_failure_becomes_a_clear_503(failure):
    client = httpx.Client(transport=httpx.MockTransport(failure))
    with pytest.raises(AppError) as exc:
        service.search_nominatim("bopal", client, limiter=NoWait())
    assert exc.value.status_code == 503 and exc.value.code == "GEOCODER_UNAVAILABLE"


# ---------- with the cache table (needs the test database) ----------

@needs_db
def test_second_search_is_answered_from_the_cache_without_calling_nominatim(db):
    client, calls = fake_nominatim()
    first = service.geocode(db, "Bopal, Ahmedabad", NOW, client, limiter=NoWait())
    second = service.geocode(db, "  BOPAL,  ahmedabad ", NOW + timedelta(hours=1), client, limiter=NoWait())
    assert first.cached is False and second.cached is True
    assert len(calls) == 1
    assert [p.name for p in second.places] == [p.name for p in first.places]
    assert db.execute(text("SELECT count(*) FROM geocode_cache")).scalar() == 1  # one row for both spellings


@needs_db
def test_old_cache_entries_are_refreshed(db):
    client, calls = fake_nominatim()
    service.geocode(db, "bopal", NOW, client, limiter=NoWait())
    again = service.geocode(db, "bopal", NOW + timedelta(days=31), client, limiter=NoWait())  # cache keeps 30 days
    assert again.cached is False and len(calls) == 2


@needs_db
def test_no_results_are_cached_too(db):
    client, calls = fake_nominatim(answer=[])
    assert service.geocode(db, "zzzzqq", NOW, client, limiter=NoWait()).places == []
    assert service.geocode(db, "zzzzqq", NOW, client, limiter=NoWait()).cached is True
    assert len(calls) == 1


@needs_db
def test_failed_searches_are_not_cached(db):
    bad, _ = fake_nominatim(status=500)
    with pytest.raises(AppError):
        service.geocode(db, "bopal", NOW, bad, limiter=NoWait())
    good, calls = fake_nominatim()
    assert service.geocode(db, "bopal", NOW, good, limiter=NoWait()).cached is False and len(calls) == 1


@needs_db
def test_too_short_a_query_is_rejected(db):
    with pytest.raises(AppError) as exc:
        service.geocode(db, " a ", NOW, fake_nominatim()[0], limiter=NoWait())
    assert exc.value.code == "QUERY_TOO_SHORT"


@needs_db
def test_http_endpoint(db_client, monkeypatch):
    client, calls = fake_nominatim()
    monkeypatch.setattr(service, "rate_limiter", NoWait())
    monkeypatch.setattr(service.httpx, "Client", lambda *a, **k: client)  # the endpoint creates its own client
    body = db_client.get("/api/geocode", params={"q": "Bopal"}).json()
    assert body["query"] == "Bopal" and body["places"][0]["name"].startswith("Bopal") and body["cached"] is False
    assert db_client.get("/api/geocode", params={"q": "a"}).status_code == 422
