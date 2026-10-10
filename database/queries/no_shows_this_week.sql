-- No-shows in the last 7 days per station: how often booked drivers never arrived.
-- Each no-show keeps the ₹199 booking fee (docs/architecture.md section 6.3).

SELECT
    s.name                          AS station,
    count(*)                        AS no_shows,
    count(*) * 199                  AS fees_kept_inr
FROM bookings b
JOIN chargers c USING (charger_id)
JOIN stations s USING (station_id)
WHERE b.status = 'NO_SHOW'
  AND lower(b.time_range) >= now() - interval '7 days'
GROUP BY s.name
ORDER BY no_shows DESC;
