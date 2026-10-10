-- Today's bookings (India time), earliest first, with station, charger and status.
-- Read-only. Open in DBeaver and run with Ctrl+Enter.

SELECT
    to_char(lower(b.time_range) AT TIME ZONE 'Asia/Kolkata', 'HH24:MI') AS starts,
    to_char(upper(b.time_range) AT TIME ZONE 'Asia/Kolkata', 'HH24:MI') AS ends,
    s.name                                                                AS station,
    c.label                                                               AS charger,
    b.status,
    b.source,
    coalesce(u.full_name, 'walk-in')                                      AS customer
FROM bookings b
JOIN chargers c USING (charger_id)
JOIN stations s USING (station_id)
LEFT JOIN users u USING (user_id)
WHERE (lower(b.time_range) AT TIME ZONE 'Asia/Kolkata')::date = (now() AT TIME ZONE 'Asia/Kolkata')::date
ORDER BY lower(b.time_range), s.name, c.label;
