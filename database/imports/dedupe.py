"""Merge duplicate stations: the same place listed by more than one source.

Two stations count as the same place when they are within ~50 m of each other AND
their names are similar (or one of them has only a generic name like "EV Charging
Station", or both have the same operator).

The surviving station is chosen by source priority: manual > ocm > osm > synthetic
(then the one with more chargers). The other station's source records are re-pointed
to the survivor, chargers it has in plug types the survivor lacks are moved over, and
it is deleted. Every merge is written to data/raw/dedupe_report.csv for a person to check.

Usage (repository root, backend venv active):
    python -m database.imports.dedupe            # merge
    python -m database.imports.dedupe --dry-run  # only write the report
"""

import argparse
import csv
import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from database.common import RAW_DIR, connect
from database.imports.normalize import GENERIC_NAME_WORDS, is_generic_name

DUPLICATE_DISTANCE_M = 50
NAME_SIMILARITY = 0.6
SOURCE_PRIORITY = {"manual": 0, "ocm": 1, "osm": 2, "synthetic": 3}


@dataclass
class Candidate:
    station_id: str
    name: str
    latitude: float
    longitude: float
    operator: str | None
    data_source: str
    charger_count: int


def distance_m(a: Candidate, b: Candidate) -> float:
    """Haversine distance in metres."""
    lat1, lng1, lat2, lng2 = map(math.radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(math.sqrt(h))


def name_key(name: str, operator: str | None) -> str:
    """Name without generic words and the operator's name, for comparison."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    operator_words = set(re.findall(r"[a-z0-9]+", (operator or "").lower()))
    return " ".join(w for w in words if w not in GENERIC_NAME_WORDS and w not in operator_words)


def same_place(a: Candidate, b: Candidate) -> bool:
    if distance_m(a, b) > DUPLICATE_DISTANCE_M:
        return False
    if is_generic_name(a.name) or is_generic_name(b.name):
        return True
    if a.operator and a.operator == b.operator:
        return True
    key_a, key_b = name_key(a.name, a.operator), name_key(b.name, b.operator)
    if not key_a or not key_b:
        return True
    return SequenceMatcher(None, key_a, key_b).ratio() >= NAME_SIMILARITY


def survivor_order(c: Candidate) -> tuple:
    return (SOURCE_PRIORITY.get(c.data_source, 9), -c.charger_count, c.station_id)


def find_duplicates(stations: list[Candidate]) -> list[tuple[Candidate, list[Candidate]]]:
    """Group stations that are the same place. Returns [(survivor, [duplicates])]."""
    parent = {s.station_id: s.station_id for s in stations}

    def root(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ordered = sorted(stations, key=lambda s: s.latitude)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if b.latitude - a.latitude > 0.001:   # ~110 m north: nothing further can be within 50 m
                break
            if same_place(a, b):
                parent[root(a.station_id)] = root(b.station_id)

    groups: dict[str, list[Candidate]] = {}
    for s in stations:
        groups.setdefault(root(s.station_id), []).append(s)

    result = []
    for members in groups.values():
        if len(members) > 1:
            members.sort(key=survivor_order)
            result.append((members[0], members[1:]))
    return result


def load_candidates(conn) -> list[Candidate]:
    rows = conn.execute(
        """
        SELECT s.station_id::text, s.name, s.latitude, s.longitude, o.name, s.data_source,
               (SELECT count(*) FROM chargers c WHERE c.station_id = s.station_id)
        FROM stations s LEFT JOIN operators o USING (operator_id)
        """
    ).fetchall()
    return [Candidate(*row) for row in rows]


def merge(conn, survivor: Candidate, duplicate: Candidate) -> int:
    """Fold one duplicate into the survivor. Returns how many chargers moved."""
    conn.execute("UPDATE station_sources SET station_id = %s WHERE station_id = %s",
                 (survivor.station_id, duplicate.station_id))
    survivor_types = {r[0] for r in conn.execute(
        "SELECT DISTINCT connector_type FROM chargers WHERE station_id = %s", (survivor.station_id,))}
    moved = 0
    for charger_id, connector_type in conn.execute(
            "SELECT charger_id, connector_type FROM chargers WHERE station_id = %s ORDER BY label",
            (duplicate.station_id,)).fetchall():
        if connector_type in survivor_types:
            continue
        taken = conn.execute("SELECT count(*) FROM chargers WHERE station_id = %s AND connector_type = %s",
                             (survivor.station_id, connector_type)).fetchone()[0]
        conn.execute("UPDATE chargers SET station_id = %s, label = %s WHERE charger_id = %s",
                     (survivor.station_id, f"{connector_type}-{taken + 1}", charger_id))
        moved += 1
    # Chargers left behind duplicate ones the survivor already has. Bookings would block
    # deleting them, but imported stations have no bookings yet.
    conn.execute("DELETE FROM stations WHERE station_id = %s", (duplicate.station_id,))
    return moved


def run(dry_run: bool = False) -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RAW_DIR / "dedupe_report.csv"
    with connect() as conn, report_path.open("w", newline="", encoding="utf-8") as report:
        writer = csv.writer(report)
        writer.writerow(["kept_station", "kept_source", "merged_station", "merged_source", "distance_m", "chargers_moved"])
        groups = find_duplicates(load_candidates(conn))
        merged = 0
        for survivor, duplicates in groups:
            for dup in duplicates:
                moved = 0 if dry_run else merge(conn, survivor, dup)
                writer.writerow([survivor.name, survivor.data_source, dup.name, dup.data_source,
                                 round(distance_m(survivor, dup)), moved])
                merged += 1
        if not dry_run:
            conn.commit()
    action = "would merge" if dry_run else "merged"
    return f"Duplicates: {action} {merged} station(s) in {len(groups)} group(s). Report: {report_path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge duplicate stations.")
    parser.add_argument("--dry-run", action="store_true", help="only write the report, change nothing")
    print(run(parser.parse_args().dry_run))


if __name__ == "__main__":
    main()
