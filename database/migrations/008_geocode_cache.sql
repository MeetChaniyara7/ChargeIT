-- 008: Cache for address searches.

-- Nominatim (OpenStreetMap's free geocoder) allows at most one request per second.
-- Remembering answers avoids asking twice for the same place.
CREATE TABLE geocode_cache (
    query      text PRIMARY KEY,                 -- normalised search text, e.g. "bopal ahmedabad"
    result     jsonb NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now()
);
