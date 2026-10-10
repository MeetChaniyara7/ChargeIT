-- 003: Charging stations and their chargers.

-- Companies that run stations ("Tata Power", "Jio-bp", ...). Spelling variants are
-- merged on import, so the name is unique.
CREATE TABLE operators (
    operator_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    website     text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stations (
    station_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name             text NOT NULL,
    address          text NOT NULL DEFAULT '',
    city             text,
    state            text,
    postcode         text,
    latitude         double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude        double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    operator_id      uuid REFERENCES operators (operator_id) ON DELETE SET NULL,
    -- Who the station is for. The app currently shows only FOUR_WHEELER stations;
    -- TWO_WHEELER stations (e.g. scooter networks) are kept for a future section.
    vehicle_category text NOT NULL DEFAULT 'FOUR_WHEELER'
                     CHECK (vehicle_category IN ('FOUR_WHEELER', 'TWO_WHEELER')),
    amenities        text[] NOT NULL DEFAULT '{}',
    opening_hours    text,
    rating           numeric(2, 1) CHECK (rating BETWEEN 0 AND 5),
    rating_count     integer NOT NULL DEFAULT 0 CHECK (rating_count >= 0),
    is_active        boolean NOT NULL DEFAULT true,
    -- The source this station's details come from.
    data_source      data_source NOT NULL,
    -- Columns whose values were generated rather than imported, e.g. {rating}.
    -- The app shows an "approximate data" badge when this is not empty.
    estimated_fields text[] NOT NULL DEFAULT '{}',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX stations_location ON stations (latitude, longitude);
CREATE INDEX stations_operator ON stations (operator_id);

CREATE TRIGGER stations_set_updated_at BEFORE UPDATE ON stations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Every outside record a station was built from, e.g. ('osm', 'node/123') or
-- ('ocm', '45678'). When duplicates are merged, the merged records keep pointing at
-- the surviving station, so re-running an import updates it instead of re-creating
-- the duplicate.
CREATE TABLE station_sources (
    data_source  data_source NOT NULL,
    external_ref text NOT NULL,
    station_id   uuid NOT NULL REFERENCES stations (station_id) ON DELETE CASCADE,
    imported_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (data_source, external_ref)
);

CREATE INDEX station_sources_station ON station_sources (station_id);

-- One row = one bookable plug. A booking always reserves exactly one charger.
CREATE TABLE chargers (
    charger_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id       uuid NOT NULL REFERENCES stations (station_id) ON DELETE CASCADE,
    label            text NOT NULL,              -- shown to users, e.g. "CCS2-1"
    connector_type   connector_type NOT NULL,
    current_type     text CHECK (current_type IN ('AC', 'DC')),
    power_kw         numeric(6, 1) CHECK (power_kw > 0),
    price_per_kwh    numeric(6, 2) CHECK (price_per_kwh >= 0),
    -- The charger's live physical state, as reported by the (simulated) charger.
    -- Whether it is free for a time slot is decided by bookings, not by this column.
    status           text NOT NULL DEFAULT 'AVAILABLE'
                     CHECK (status IN ('AVAILABLE', 'RESERVED', 'CHARGING', 'FAULTED', 'OUT_OF_SERVICE')),
    data_source      data_source NOT NULL,
    estimated_fields text[] NOT NULL DEFAULT '{}',   -- e.g. {price_per_kwh}
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (station_id, label)
);

CREATE INDEX chargers_station ON chargers (station_id);

CREATE TRIGGER chargers_set_updated_at BEFORE UPDATE ON chargers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Great-circle distance in kilometres between two points (the haversine formula).
-- Used for "stations near me" and duplicate detection.
CREATE OR REPLACE FUNCTION haversine_km(lat1 double precision, lng1 double precision,
                                        lat2 double precision, lng2 double precision)
RETURNS double precision
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT 2 * 6371.0088 * asin(sqrt(
        power(sin(radians(lat2 - lat1) / 2), 2)
        + cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians(lng2 - lng1) / 2), 2)
    ));
$$;
