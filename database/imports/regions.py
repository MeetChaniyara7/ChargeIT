"""Which part of India to import, and an exact "is this point inside it?" test.

The region is a setting (IMPORT_REGION in backend/.env, default "gujarat"), so other
states can be added later by adding an entry to REGIONS.

Some Open Charge Map records name the wrong state (an Ahmedabad charger labelled
"Karnataka"), so instead of trusting the state text we test each point against the
state's official boundary from OpenStreetMap.
"""

import os
from dataclasses import dataclass

from database.imports.sources import overpass


@dataclass(frozen=True)
class Region:
    key: str
    name: str
    iso_code: str                                    # OpenStreetMap ISO3166-2 code
    bbox: tuple[float, float, float, float]          # south, west, north, east (generous)


REGIONS = {
    "gujarat": Region("gujarat", "Gujarat", "IN-GJ", (20.0, 68.0, 24.8, 74.6)),
}


def current_region() -> Region:
    key = os.getenv("IMPORT_REGION", "gujarat").strip().lower()
    if key not in REGIONS:
        raise SystemExit(f"Unknown IMPORT_REGION '{key}'. Known: {', '.join(REGIONS)}")
    return REGIONS[key]


Segment = tuple[float, float, float, float]  # lng1, lat1, lng2, lat2


def boundary_segments(region: Region) -> list[Segment]:
    """Every edge of the region's outer boundary (downloaded once, then cached)."""
    query = f'[out:json][timeout:120];rel["ISO3166-2"="{region.iso_code}"]["boundary"="administrative"];out geom;'
    data = overpass(query, cache_name=f"boundary_{region.key}")
    segments: list[Segment] = []
    for relation in data["elements"]:
        for member in relation.get("members", []):
            if member.get("type") != "way" or member.get("role") not in ("outer", ""):
                continue
            points = member.get("geometry") or []
            for a, b in zip(points, points[1:]):
                segments.append((a["lon"], a["lat"], b["lon"], b["lat"]))
    if not segments:
        raise SystemExit(f"Could not download the boundary of {region.name}.")
    return segments


def point_in_boundary(lat: float, lng: float, segments: list[Segment]) -> bool:
    """Ray casting: draw a line from the point towards the east and count how many
    boundary edges it crosses. An odd count means the point is inside.

    This works on the boundary's edges in any order, so the outline never has to be
    stitched together into rings first.
    """
    inside = False
    for x1, y1, x2, y2 in segments:
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if x_cross > lng:
                inside = not inside
    return inside
