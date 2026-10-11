"""Address and place search through Nominatim (OpenStreetMap's free geocoder).

Nominatim's usage policy, which this module follows:
  - at most ONE request per second, from the whole application      -> RateLimiter
  - a User-Agent that identifies the app                            -> EXTERNAL_SERVICES.user_agent
  - cache results instead of asking twice                           -> geocode_cache table
  - no search-as-you-type: the web app only calls this on "submit"  -> see the Explore screen
"""

import json
import logging
import re
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import EXTERNAL_SERVICES, ExternalServices
from app.core.errors import AppError
from app.features.geocoding.schemas import GeocodeResponse, Place

logger = logging.getLogger(__name__)


class RateLimiter:
    """Lets one call through every `min_interval` seconds, across all threads."""

    def __init__(self, min_interval: float, max_wait: float, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self._min_interval, self._max_wait = min_interval, max_wait
        self._clock, self._sleep = clock, sleep
        self._next_free = 0.0
        self._lock = threading.Lock()

    def wait_turn(self) -> None:
        """Block until it is this caller's turn; refuse if the queue is too long."""
        with self._lock:
            now = self._clock()
            start = max(now, self._next_free)
            if start - now > self._max_wait:
                raise AppError(429, "SEARCH_BUSY", "Place search is busy. Please try again in a moment.")
            self._next_free = start + self._min_interval
            delay = start - now
        if delay > 0:
            self._sleep(delay)


rate_limiter = RateLimiter(EXTERNAL_SERVICES.nominatim_min_interval_seconds, EXTERNAL_SERVICES.nominatim_max_wait_seconds)


def normalize_query(q: str) -> str:
    """'  Bopal,   AHMEDABAD ' -> 'bopal, ahmedabad' (so the same search always hits the same cache row)."""
    return re.sub(r"\s+", " ", q.strip().lower())


def _parse(results: list[dict]) -> list[Place]:
    places = []
    for item in results:
        try:
            bbox = item.get("boundingbox")
            places.append(
                Place(
                    name=item["display_name"],
                    lat=float(item["lat"]),
                    lng=float(item["lon"]),
                    bbox=tuple(float(v) for v in bbox) if bbox and len(bbox) == 4 else None,
                    kind=item.get("type"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip a malformed entry rather than fail the whole search
    return places


def search_nominatim(query: str, client: httpx.Client, services: ExternalServices = EXTERNAL_SERVICES, limiter: RateLimiter = rate_limiter) -> list[Place]:
    limiter.wait_turn()
    try:
        response = client.get(
            f"{services.nominatim_base_url}/search",
            params={
                "q": query, "format": "jsonv2", "countrycodes": "in", "limit": 5,
                "viewbox": services.nominatim_viewbox, "bounded": 0,
            },
            headers={"User-Agent": services.user_agent},
            timeout=services.nominatim_timeout_seconds,
        )
        response.raise_for_status()
        return _parse(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Nominatim failed for %r: %s", query, exc)
        raise AppError(503, "GEOCODER_UNAVAILABLE", "Place search is unavailable right now.") from exc


def geocode(
    db: Session,
    q: str,
    now: datetime | None = None,
    client: httpx.Client | None = None,
    services: ExternalServices = EXTERNAL_SERVICES,
    limiter: RateLimiter = rate_limiter,
) -> GeocodeResponse:
    now = now or datetime.now(timezone.utc)
    key = normalize_query(q)
    if len(key) < 2:
        raise AppError(422, "QUERY_TOO_SHORT", "Type at least 2 characters to search.")

    fresh_after = now - timedelta(days=services.nominatim_cache_days)
    row = db.execute(
        text("SELECT result FROM geocode_cache WHERE query = :q AND fetched_at > :fresh"), {"q": key, "fresh": fresh_after}
    ).first()
    if row:
        return GeocodeResponse(query=q.strip(), places=[Place(**p) for p in row[0]], cached=True)

    own_client = client is None
    client = client or httpx.Client()
    try:
        places = search_nominatim(key, client, services, limiter)
    finally:
        if own_client:
            client.close()

    db.execute(
        text(
            "INSERT INTO geocode_cache (query, result, fetched_at) VALUES (:q, CAST(:r AS jsonb), :now) "
            "ON CONFLICT (query) DO UPDATE SET result = EXCLUDED.result, fetched_at = EXCLUDED.fetched_at"
        ),
        {"q": key, "r": json.dumps([p.model_dump() for p in places]), "now": now},
    )
    db.commit()
    return GeocodeResponse(query=q.strip(), places=places, cached=False)
