"""Drive times from OSRM (free public routing server), with a safe fallback.

One request asks for the drive time from the driver to ALL candidate stations at once.
If OSRM is slow (over 3 seconds), unreachable or confused, we fall back to straight-line
distance at an assumed city speed (25 km/h). Recommendations therefore never fail just
because a free public service is having a bad day, and each result says whether its time
is real ("routed") or an estimate.

After a failure we don't ask again for a short while, so a down service can't slow every request.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.config import EXTERNAL_SERVICES, RECOMMENDATION_RULES, ExternalServices, RecommendationRules
from app.core.geo import haversine_km

logger = logging.getLogger(__name__)

Point = tuple[float, float]  # (lat, lng)
RETRY_AFTER_FAILURE_SECONDS = 30
CACHE_LIMIT = 256


@dataclass(frozen=True)
class Travel:
    minutes: float
    distance_km: float
    routed: bool  # True = real road time from OSRM; False = straight-line estimate


class TravelTimes:
    def __init__(
        self,
        client: httpx.Client | None = None,
        services: ExternalServices = EXTERNAL_SERVICES,
        rules: RecommendationRules = RECOMMENDATION_RULES,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = client or httpx.Client(timeout=services.osrm_timeout_seconds, headers={"User-Agent": services.user_agent})
        self._services = services
        self._rules = rules
        self._clock = clock
        self._cache: dict[tuple, tuple[float, list[Travel]]] = {}
        self._failed_at: float | None = None

    # -- the fallback ---------------------------------------------------------------

    def straight_line(self, origin: Point, destinations: list[Point]) -> list[Travel]:
        result = []
        for lat, lng in destinations:
            km = haversine_km(origin[0], origin[1], lat, lng)
            result.append(Travel(minutes=km / self._rules.drive_speed_kmh * 60, distance_km=km, routed=False))
        return result

    # -- the real thing -------------------------------------------------------------

    def _ask_osrm(self, origin: Point, destinations: list[Point]) -> list[Travel]:
        coordinates = ";".join(f"{lng},{lat}" for lat, lng in [origin, *destinations])
        indexes = ";".join(str(i) for i in range(1, len(destinations) + 1))
        response = self._client.get(
            f"{self._services.osrm_base_url}/table/v1/driving/{coordinates}",
            params={"sources": "0", "destinations": indexes, "annotations": "duration,distance"},
            timeout=self._services.osrm_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != "Ok":
            raise ValueError(f"OSRM said {body.get('code')}")
        durations, distances = body["durations"][0], body["distances"][0]
        fallback = self.straight_line(origin, destinations)
        # A destination OSRM can't reach (null) keeps its straight-line estimate.
        return [
            Travel(durations[i] / 60, distances[i] / 1000, True) if durations[i] is not None and distances[i] is not None else fallback[i]
            for i in range(len(destinations))
        ]

    def estimate(self, origin: Point, destinations: list[Point]) -> list[Travel]:
        """Travel from origin to every destination, in the same order."""
        if not destinations:
            return []
        now = self._clock()
        key = (round(origin[0], 3), round(origin[1], 3), tuple((round(a, 4), round(b, 4)) for a, b in destinations))

        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

        if self._failed_at is not None and now - self._failed_at < RETRY_AFTER_FAILURE_SECONDS:
            return self.straight_line(origin, destinations)  # recently failed: don't wait for it again

        try:
            result = self._ask_osrm(origin, destinations)
            self._failed_at = None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("OSRM unavailable, using straight-line estimates: %s", exc)
            self._failed_at = now
            return self.straight_line(origin, destinations)

        if len(self._cache) >= CACHE_LIMIT:
            self._cache.clear()
        self._cache[key] = (now + self._services.osrm_cache_seconds, result)
        return result


# One shared instance for the whole API (it keeps the cache and the "recently failed" memory).
travel_times = TravelTimes()
