-- 006: Charging sessions and charger events.

-- One row per time a charger actually delivers energy.
CREATE TABLE charging_sessions (
    session_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- The booking this session fulfils. Empty only for EXTERNAL sessions (someone used
    -- the operator's own app or card), which ChargeSpot sees but did not book.
    booking_id        uuid UNIQUE REFERENCES bookings (booking_id) ON DELETE RESTRICT,
    charger_id        uuid NOT NULL REFERENCES chargers (charger_id) ON DELETE RESTRICT,
    device_id         uuid REFERENCES station_devices (device_id) ON DELETE SET NULL,
    source            text NOT NULL CHECK (source IN ('BOOKING', 'WALK_IN', 'EXTERNAL')),
    started_at        timestamptz NOT NULL DEFAULT now(),
    ended_at          timestamptz,
    end_reason        text CHECK (end_reason IN
                          ('USER_STOP', 'SLOT_END_AUTO_STOP', 'NEXT_BOOKING_AUTO_STOP',
                           'PREPAID_USED', 'UNPLUGGED', 'ADMIN')),
    start_soc_percent numeric(5, 2) CHECK (start_soc_percent BETWEEN 0 AND 100),
    energy_kwh        numeric(10, 3) NOT NULL DEFAULT 0 CHECK (energy_kwh >= 0),
    bill_amount       money_inr,                 -- energy x price, set when the session ends
    bill_status       text CHECK (bill_status IN ('DUE', 'PAID', 'PREPAID_SETTLED')),
    prepaid_amount    money_inr,                 -- walk-ins pay before charging
    paid_at           timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),

    -- Sessions started through ChargeSpot always have a booking; outside ones never do.
    CONSTRAINT charging_sessions_booking_matches_source
        CHECK ((source = 'EXTERNAL') = (booking_id IS NULL)),
    CONSTRAINT charging_sessions_end_after_start
        CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- A charger can only run one session at a time.
CREATE UNIQUE INDEX charging_sessions_one_running_per_charger
    ON charging_sessions (charger_id) WHERE ended_at IS NULL;

CREATE INDEX charging_sessions_bill_due ON charging_sessions (bill_status) WHERE bill_status = 'DUE';

-- Log of everything a (simulated) charger reports, in the style of the OCPP protocol
-- real chargers use: started, stopped, reserved, faulted, ... The event names are
-- defined with the charger simulator in Phase 5.
CREATE TABLE charger_events (
    event_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    charger_id uuid NOT NULL REFERENCES chargers (charger_id) ON DELETE CASCADE,
    event      text NOT NULL,
    source     text NOT NULL DEFAULT 'SIMULATOR',
    details    jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX charger_events_charger_time ON charger_events (charger_id, created_at DESC);
