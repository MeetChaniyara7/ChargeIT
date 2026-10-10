-- 002: People and their cars.

-- Accounts from Google sign-in or email registration. Columns and IDs match the old
-- database, so existing users can be copied across and keep their logins.
CREATE TABLE users (
    user_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email          text NOT NULL,
    full_name      text,
    phone          text,
    google_user_id text UNIQUE,
    password_hash  text,                       -- empty for Google-only accounts
    role           text NOT NULL DEFAULT 'USER' CHECK (role IN ('USER', 'ADMIN')),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

-- One account per email address, ignoring upper/lower case.
CREATE UNIQUE INDEX users_email_unique ON users (lower(email));

CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- A user's vehicles. The connector decides which chargers fit; the battery size caps
-- how much energy a charging session can deliver.
CREATE TABLE vehicles (
    vehicle_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    nickname       text NOT NULL,
    connector_type connector_type NOT NULL,
    battery_kwh    numeric(5, 1) NOT NULL CHECK (battery_kwh > 0 AND battery_kwh <= 250),
    is_default     boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX vehicles_user ON vehicles (user_id);

-- At most one default vehicle per user (a "partial" unique index: it only covers rows
-- where is_default is true).
CREATE UNIQUE INDEX vehicles_one_default_per_user ON vehicles (user_id) WHERE is_default;
