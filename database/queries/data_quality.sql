-- How much of the station data is real and how much is generated.
-- "estimated" = a real charger with some values filled in (e.g. price), "synthetic" = a generated charger.

SELECT
    s.data_source                                                   AS station_source,
    count(DISTINCT s.station_id)                                    AS stations,
    count(c.charger_id)                                             AS chargers,
    count(c.charger_id) FILTER (WHERE c.data_source = 'synthetic')  AS synthetic_chargers,
    count(c.charger_id) FILTER (WHERE c.data_source <> 'synthetic'
                                  AND cardinality(c.estimated_fields) > 0) AS chargers_with_estimates,
    count(c.charger_id) FILTER (WHERE c.data_source <> 'synthetic'
                                  AND cardinality(c.estimated_fields) = 0) AS fully_real_chargers
FROM stations s
LEFT JOIN chargers c USING (station_id)
WHERE s.vehicle_category = 'FOUR_WHEELER'
GROUP BY s.data_source
ORDER BY stations DESC;
