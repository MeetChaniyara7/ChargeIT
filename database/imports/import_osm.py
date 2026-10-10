"""Import charging stations from OpenStreetMap (amenity=charging_station) for the region.

Usage (repository root, backend venv active):
    python -m database.imports.import_osm            # uses the cached download if present
    python -m database.imports.import_osm --refresh  # download fresh data
"""

import argparse
from collections import defaultdict

from database.common import connect
from database.imports.normalize import classify, clean_station_name, connectors_from_osm_tags, normalize_operator
from database.imports.regions import Region, current_region
from database.imports.sources import overpass
from database.imports.store import ChargerData, StationData, upsert_station


def fetch(region: Region, refresh: bool) -> list[dict]:
    query = (
        f'[out:json][timeout:120];area["ISO3166-2"="{region.iso_code}"]["boundary"="administrative"]->.r;'
        'nwr["amenity"="charging_station"](area.r);out center tags;'
    )
    return overpass(query, cache_name=f"osm_stations_{region.key}", refresh=refresh)["elements"]


def to_station(element: dict, region: Region) -> StationData | None:
    tags = element.get("tags", {})
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lng = element.get("lon") or element.get("center", {}).get("lon")
    if lat is None or lng is None:
        return None

    raw_name = tags.get("name") or tags.get("name:en")
    operator = normalize_operator(tags.get("operator"), tags.get("brand"), tags.get("network"), station_name=raw_name)
    category = classify(raw_name, operator, tags=tags)
    if category == "EXCLUDE":
        return None

    area = tags.get("addr:suburb") or tags.get("addr:city") or tags.get("addr:district")
    address = ", ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb")) if p)
    chargers = [
        ChargerData(c["connector_type"], c["power_kw"], None, "osm")
        for c in connectors_from_osm_tags(tags)
        for _ in range(c["count"])
    ]
    return StationData(
        data_source="osm",
        external_ref=f"{element['type']}/{element['id']}",
        name=clean_station_name(raw_name, operator, area),
        address=address,
        city=tags.get("addr:city"),
        state=region.name,
        postcode=tags.get("addr:postcode"),
        latitude=float(lat),
        longitude=float(lng),
        operator=operator,
        vehicle_category=category,
        opening_hours=tags.get("opening_hours"),
        chargers=chargers,
    )


def run(refresh: bool = False) -> str:
    region = current_region()
    elements = fetch(region, refresh)
    outcomes = defaultdict(int)
    with connect() as conn:
        for element in elements:
            station = to_station(element, region)
            if station is None:
                outcomes["skipped (not a bookable car/scooter charger)"] += 1
                continue
            _, outcome = upsert_station(conn, station)
            outcomes[outcome] += 1
        conn.commit()
    return f"OpenStreetMap ({region.name}): {len(elements)} records -> {dict(outcomes)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="download fresh data instead of using the cache")
    print(run(parser.parse_args().refresh))


if __name__ == "__main__":
    main()
