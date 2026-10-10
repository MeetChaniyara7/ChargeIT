"""Import charging stations from Open Charge Map for the region.

Open Charge Map is searched by bounding box, which also catches some places just over
the border; each point is then checked against the region's real boundary. Records whose
address names a different state are skipped, because their coordinates are wrong.

Usage (repository root, backend venv active):
    python -m database.imports.import_ocm            # uses the cached download if present
    python -m database.imports.import_ocm --refresh  # download fresh data
"""

import argparse
from collections import defaultdict

from database.common import connect
from database.imports.normalize import (
    classify, clean_station_name, connector_from_title, names_other_state, normalize_operator, parse_price_per_kwh,
)
from database.imports.regions import Region, boundary_segments, current_region, point_in_boundary
from database.imports.sources import open_charge_map
from database.imports.store import ChargerData, StationData, upsert_station

NOT_OPERATIONAL_STATUS_IDS = {100, 150, 200, 210}   # Open Charge Map: not operational / removed


def fetch(region: Region, refresh: bool) -> list[dict]:
    south, west, north, east = region.bbox
    params = {"countrycode": "IN", "boundingbox": f"({south},{west}),({north},{east})"}
    return open_charge_map(params, cache_name=f"ocm_stations_{region.key}", refresh=refresh)


def to_station(poi: dict, region: Region) -> StationData | None:
    info = poi.get("AddressInfo") or {}
    connections = poi.get("Connections") or []
    titles = [(c.get("ConnectionType") or {}).get("Title") for c in connections]

    raw_name = info.get("Title")
    operator = normalize_operator((poi.get("OperatorInfo") or {}).get("Title"), station_name=raw_name)
    category = classify(raw_name, operator, plug_titles=titles)
    if category == "EXCLUDE":
        return None

    price = parse_price_per_kwh(poi.get("UsageCost"))
    chargers = []
    for c in connections:
        title = (c.get("ConnectionType") or {}).get("Title")
        connector = connector_from_title(title, (c.get("CurrentType") or {}).get("Title"))
        if connector is None:
            continue   # unknown or scooter-only plug: details filled in later
        for _ in range(min(max(int(c.get("Quantity") or 1), 1), 10)):
            chargers.append(ChargerData(connector, c.get("PowerKW") or None, price, "ocm"))

    status_id = (poi.get("StatusType") or {}).get("ID") or poi.get("StatusTypeID")
    area = info.get("Town")
    return StationData(
        data_source="ocm",
        external_ref=str(poi["ID"]),
        name=clean_station_name(raw_name, operator, area),
        address=", ".join(p for p in (info.get("AddressLine1"), info.get("AddressLine2")) if p),
        city=area,
        state=region.name,
        postcode=info.get("Postcode"),
        latitude=float(info["Latitude"]),
        longitude=float(info["Longitude"]),
        operator=operator,
        vehicle_category=category,
        is_active=status_id not in NOT_OPERATIONAL_STATUS_IDS,
        chargers=chargers,
    )


def run(refresh: bool = False) -> str:
    region = current_region()
    pois = fetch(region, refresh)
    boundary = boundary_segments(region)
    outcomes = defaultdict(int)
    with connect() as conn:
        for poi in pois:
            info = poi.get("AddressInfo") or {}
            if not point_in_boundary(info["Latitude"], info["Longitude"], boundary):
                outcomes[f"skipped (outside {region.name})"] += 1
                continue
            # Some records are pinned inside the region but their address is in another
            # state (e.g. a Bengaluru charger placed in Ahmedabad). Their location can't be trusted.
            if names_other_state(region.name, info.get("StateOrProvince"), info.get("AddressLine1"),
                                 info.get("AddressLine2"), info.get("Town")):
                outcomes["skipped (address contradicts location)"] += 1
                continue
            station = to_station(poi, region)
            if station is None:
                outcomes["skipped (not a bookable charger)"] += 1
                continue
            _, outcome = upsert_station(conn, station)
            outcomes[outcome] += 1
        conn.commit()
    return f"Open Charge Map ({region.name}): {len(pois)} records -> {dict(outcomes)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="download fresh data instead of using the cache")
    print(run(parser.parse_args().refresh))


if __name__ == "__main__":
    main()
