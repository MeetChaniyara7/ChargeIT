-- 005: Station kiosks.

-- Each station has one kiosk tablet, which signs in with its own API key.
-- Only a SHA-256 hash of the key is stored; the key itself is shown once when created.
CREATE TABLE station_devices (
    device_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id   uuid NOT NULL REFERENCES stations (station_id) ON DELETE CASCADE,
    name         text NOT NULL,
    key_prefix   text NOT NULL UNIQUE,           -- first characters of the key, to tell keys apart
    api_key_hash text NOT NULL UNIQUE,
    is_active    boolean NOT NULL DEFAULT true,
    last_seen_at timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX station_devices_station ON station_devices (station_id);

-- Every OTP typed at a kiosk, right or wrong. Used for the wrong-guess cooldown
-- (5 wrong tries -> 2-minute pause) and the admin alert (20+ wrong in 10 minutes).
CREATE TABLE otp_attempts (
    attempt_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id  uuid NOT NULL REFERENCES station_devices (device_id) ON DELETE CASCADE,
    success    boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX otp_attempts_device_time ON otp_attempts (device_id, created_at DESC);
