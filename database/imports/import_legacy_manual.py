"""Import the 10 hand-verified Ahmedabad stations from the old database's CSV exports.

These rows (station IDs VERIFY-ST-001 ... VERIFY-ST-010) were entered and checked by
the team, so they are tagged data_source = 'manual' and win over any imported duplicate.
Every other station in the old export is ignored: real data is re-imported cleanly from
OpenStreetMap and Open Charge Map instead.

Usage (repository root, backend venv active):
    python -m database.imports.import_legacy_manual
"""

import csv
from collections import defaultdict
from pathlib import Path

from database.common import LEGACY_DIR, connect
from database.imports.normalize import normalize_operator
from database.imports.store import ChargerData, StationData, upsert_station
from database.seeds.profiles import generate_chargers

LEGACY_CONNECTORS = {"CCS2": "CCS2", "CHADEMO": "CHADEMO", "TYPE2": "TYPE2", "GB_T": "BHARAT_DC001"}


def read_csv(prefix: str) -> list[dict]:
    files = sorted(LEGACY_DIR.glob(f"{prefix}_*.csv"))
    if not files:
        raise SystemExit(f"No {prefix}_*.csv in {LEGACY_DIR}. Copy the old database exports there first.")
    with Path(files[-1]).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def positive(value: str | None) -> float | None:
    try:
        number = float(value) if value not in (None, "") else None
    except ValueError:
        return None
    return number if number and number > 0 else None


def load_manual_stations() -> list[StationData]:
    stations = [s for s in read_csv("stations") if (s.get("osm_id") or "").startswith("VERIFY-ST-")]
    operators = {o["operator_id"]: o["operator_name"] for o in read_csv("operators")}
    chargers_by_station = defaultdict(list)
    for c in read_csv("chargers"):
        chargers_by_station[c["station_id"]].append(c)
    connector_by_charger = {c["charger_id"]: c for c in read_csv("connectors")}

    result = []
    for s in stations:
        operator = normalize_operator(operators.get(s["operator_id"]))
        chargers = []
        for c in chargers_by_station.get(s["station_id"], []):
            connector = connector_by_charger.get(c["charger_id"], {})
            chargers.append(ChargerData(
                connector_type=LEGACY_CONNECTORS.get(c["connector_type"], "OTHER"),
                power_kw=positive(c.get("power_kw")) or positive(connector.get("power_kw")),
                price_per_kwh=positive(connector.get("price_per_kwh")),   # 0 in the export means "not recorded"
                data_source="manual",
            ))

        # The team recorded how many chargers each station has, but not always each one's
        # details. Top up to that count with plausible chargers, clearly marked synthetic.
        declared = int(float(s.get("total_chargers") or 0))
        missing = declared - len(chargers)
        if missing > 0:
            for g in generate_chargers(s["station_id"], operator, count=missing):
                chargers.append(ChargerData(g["connector_type"], g["power_kw"], g["price_per_kwh"], "synthetic"))

        always_open = s.get("opening_time") == "00:00" and s.get("closing_time") == "23:59"
        result.append(StationData(
            data_source="manual",
            external_ref=s["osm_id"],
            name=s["station_name"].strip(),
            address=s.get("address") or "",
            city=s.get("city") or None,
            state=s.get("state") or None,
            postcode=s.get("postal_code") or None,
            latitude=float(s["latitude"]),
            longitude=float(s["longitude"]),
            operator=operator,
            opening_hours="24/7" if always_open else None,
            chargers=chargers,
        ))
    return result


def run() -> str:
    stations = load_manual_stations()
    outcomes = defaultdict(int)
    with connect() as conn:
        for s in stations:
            _, outcome = upsert_station(conn, s)
            outcomes[outcome] += 1
        conn.commit()
    return f"Manual stations: {len(stations)} read -> {dict(outcomes)}"


if __name__ == "__main__":
    print(run())
