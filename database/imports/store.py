"""Database writes shared by every importer. Designed so imports can be re-run safely.

How re-running stays safe:
- Each outside record (e.g. OSM node/123) is remembered in station_sources. Importing it
  again finds the same station and updates it instead of creating a duplicate.
- If duplicate removal merged that record into another station, the record now points
  at the surviving station, and the importer leaves that station's details alone
  (it belongs to a higher-priority source).
- Chargers are matched by their label ("CCS2-1"), so re-importing updates them in place
  and never deletes a charger that bookings might reference.
"""

from dataclasses import dataclass, field

import psycopg

from database.imports.normalize import current_type_for


@dataclass
class ChargerData:
    connector_type: str
    power_kw: float | None = None
    price_per_kwh: float | None = None
    data_source: str = "osm"
    estimated_fields: list[str] = field(default_factory=list)


@dataclass
class StationData:
    data_source: str
    external_ref: str
    name: str
    latitude: float
    longitude: float
    address: str = ""
    city: str | None = None
    state: str | None = None
    postcode: str | None = None
    operator: str | None = None
    vehicle_category: str = "FOUR_WHEELER"
    opening_hours: str | None = None
    is_active: bool = True
    chargers: list[ChargerData] = field(default_factory=list)


def operator_id(conn: psycopg.Connection, name: str | None) -> str | None:
    if not name:
        return None
    row = conn.execute(
        "INSERT INTO operators (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
        "RETURNING operator_id",
        (name,),
    ).fetchone()
    return row[0]


def upsert_station(conn: psycopg.Connection, s: StationData) -> tuple[str, str]:
    """Create or update a station from one source record.

    Returns (station_id, outcome) where outcome is 'created', 'updated' or 'merged'
    ('merged' = the record belongs to a station owned by a higher-priority source).
    """
    found = conn.execute(
        "SELECT ss.station_id, st.data_source FROM station_sources ss "
        "JOIN stations st USING (station_id) WHERE ss.data_source = %s AND ss.external_ref = %s",
        (s.data_source, s.external_ref),
    ).fetchone()
    op_id = operator_id(conn, s.operator)
    values = (s.name, s.address or "", s.city, s.state, s.postcode, s.latitude, s.longitude,
              op_id, s.vehicle_category, s.opening_hours, s.is_active)

    if found and found[1] != s.data_source:
        conn.execute("UPDATE station_sources SET imported_at = now() WHERE data_source = %s AND external_ref = %s",
                     (s.data_source, s.external_ref))
        return found[0], "merged"

    if found:
        station_id = found[0]
        conn.execute(
            "UPDATE stations SET name=%s, address=%s, city=%s, state=%s, postcode=%s, latitude=%s, longitude=%s, "
            "operator_id=%s, vehicle_category=%s, opening_hours=%s, is_active=%s WHERE station_id=%s",
            (*values, station_id),
        )
        conn.execute("UPDATE station_sources SET imported_at = now() WHERE data_source = %s AND external_ref = %s",
                     (s.data_source, s.external_ref))
        outcome = "updated"
    else:
        station_id = conn.execute(
            "INSERT INTO stations (name, address, city, state, postcode, latitude, longitude, operator_id, "
            "vehicle_category, opening_hours, is_active, data_source) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING station_id",
            (*values, s.data_source),
        ).fetchone()[0]
        conn.execute("INSERT INTO station_sources (data_source, external_ref, station_id) VALUES (%s, %s, %s)",
                     (s.data_source, s.external_ref, station_id))
        outcome = "created"

    sync_chargers(conn, station_id, s.chargers)
    return station_id, outcome


def label_chargers(chargers: list[ChargerData]) -> list[tuple[str, ChargerData]]:
    """Give each charger a stable label: CCS2-1, CCS2-2, TYPE2-1, ..."""
    counts: dict[str, int] = {}
    labelled = []
    for c in chargers:
        counts[c.connector_type] = counts.get(c.connector_type, 0) + 1
        labelled.append((f"{c.connector_type}-{counts[c.connector_type]}", c))
    return labelled


def sync_chargers(conn: psycopg.Connection, station_id: str, chargers: list[ChargerData]) -> None:
    """Insert new chargers and refresh imported ones. Never deletes (bookings may point at them)
    and never overwrites a value someone entered by hand."""
    for label, c in label_chargers(chargers):
        conn.execute(
            """
            INSERT INTO chargers (station_id, label, connector_type, current_type, power_kw, price_per_kwh,
                                  data_source, estimated_fields)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (station_id, label) DO UPDATE SET
                power_kw      = COALESCE(EXCLUDED.power_kw, chargers.power_kw),
                price_per_kwh = COALESCE(EXCLUDED.price_per_kwh, chargers.price_per_kwh),
                estimated_fields = CASE
                    WHEN EXCLUDED.power_kw IS NOT NULL OR EXCLUDED.price_per_kwh IS NOT NULL
                    THEN array(SELECT f FROM unnest(chargers.estimated_fields) f
                               WHERE NOT (f = 'power_kw' AND EXCLUDED.power_kw IS NOT NULL)
                                 AND NOT (f = 'price_per_kwh' AND EXCLUDED.price_per_kwh IS NOT NULL))
                    ELSE chargers.estimated_fields END
            WHERE chargers.data_source = EXCLUDED.data_source
            """,
            (station_id, label, c.connector_type, current_type_for(c.connector_type), c.power_kw,
             c.price_per_kwh, c.data_source, c.estimated_fields),
        )
