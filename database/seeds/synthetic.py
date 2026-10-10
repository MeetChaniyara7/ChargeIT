"""Fill gaps in real station data with plausible, clearly-labelled values.

1. Four-wheeler stations with no chargers get a typical set for their operator
   (tagged data_source = 'synthetic').
2. Chargers missing power or price get an estimate (listed in estimated_fields).
3. Stations without a rating get one (listed in estimated_fields).

Only empty values are filled, never real ones, so this is safe to re-run. The app shows
an "approximate data" badge wherever a value is synthetic or estimated.

Usage (repository root, backend venv active):
    python -m database.seeds.synthetic
"""

from database.common import connect
from database.imports.store import ChargerData, sync_chargers
from database.seeds.profiles import estimate_power, estimate_price, estimate_rating, generate_chargers


def run() -> str:
    with connect() as conn:
        empty = conn.execute(
            """
            SELECT s.station_id::text, o.name FROM stations s LEFT JOIN operators o USING (operator_id)
            WHERE s.vehicle_category = 'FOUR_WHEELER'
              AND NOT EXISTS (SELECT 1 FROM chargers c WHERE c.station_id = s.station_id)
            """
        ).fetchall()
        for station_id, operator in empty:
            chargers = [ChargerData(g["connector_type"], g["power_kw"], g["price_per_kwh"], "synthetic")
                        for g in generate_chargers(station_id, operator)]
            sync_chargers(conn, station_id, chargers)

        missing_power = conn.execute(
            "SELECT charger_id, station_id::text, label, connector_type FROM chargers WHERE power_kw IS NULL"
        ).fetchall()
        for charger_id, station_id, label, connector in missing_power:
            conn.execute(
                "UPDATE chargers SET power_kw = %s, estimated_fields = array_append(estimated_fields, 'power_kw') "
                "WHERE charger_id = %s",
                (estimate_power(station_id, label, connector), charger_id),
            )

        missing_price = conn.execute(
            "SELECT charger_id, station_id::text, label, power_kw FROM chargers WHERE price_per_kwh IS NULL"
        ).fetchall()
        for charger_id, station_id, label, power in missing_price:
            conn.execute(
                "UPDATE chargers SET price_per_kwh = %s, estimated_fields = array_append(estimated_fields, 'price_per_kwh') "
                "WHERE charger_id = %s",
                (estimate_price(station_id, label, float(power)), charger_id),
            )

        unrated = conn.execute("SELECT station_id::text FROM stations WHERE rating IS NULL").fetchall()
        for (station_id,) in unrated:
            rating, count = estimate_rating(station_id)
            conn.execute(
                "UPDATE stations SET rating = %s, rating_count = %s, "
                "estimated_fields = array_append(estimated_fields, 'rating') WHERE station_id = %s",
                (rating, count, station_id),
            )
        conn.commit()

    return (f"Synthetic data: chargers generated for {len(empty)} station(s); estimated power for "
            f"{len(missing_power)}, price for {len(missing_price)} charger(s); ratings for {len(unrated)} station(s).")


if __name__ == "__main__":
    print(run())
