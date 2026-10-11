"""Straight-line distance and a rough drive-time estimate (used when real routing is unavailable)."""

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres between two points. Same formula as the SQL function."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lat, d_lng = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def estimate_drive_minutes(distance_km: float, speed_kmh: float) -> int:
    """Minutes to cover a distance at a steady speed, rounded up (and at least 1)."""
    return max(1, math.ceil(distance_km / speed_kmh * 60))


def bbox_around(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """A rectangle (min_lng, min_lat, max_lng, max_lat) that contains the circle, for cheap pre-filtering."""
    d_lat = math.degrees(radius_km / EARTH_RADIUS_KM)
    d_lng = math.degrees(radius_km / (EARTH_RADIUS_KM * max(math.cos(math.radians(lat)), 0.01)))
    return lng - d_lng, lat - d_lat, lng + d_lng, lat + d_lat
