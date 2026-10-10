-- 004: Bookings. The two most important rules in ChargeSpot are enforced here, by
-- PostgreSQL itself, so no bug in application code can break them:
--   1. A charger can never be booked twice for overlapping times.
--   2. A booking can only move between statuses along the allowed paths.

CREATE TABLE bookings (
    booking_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Empty only for kiosk walk-ins, who have no account (see the CHECK below).
    user_id         uuid REFERENCES users (user_id) ON DELETE RESTRICT,
    charger_id      uuid NOT NULL REFERENCES chargers (charger_id) ON DELETE RESTRICT,
    vehicle_id      uuid REFERENCES vehicles (vehicle_id) ON DELETE SET NULL,
    -- APP = booked ahead (₹199 fee), INSTANT = "Charge now" in the app, WALK_IN = kiosk QR.
    source          text NOT NULL CHECK (source IN ('APP', 'INSTANT', 'WALK_IN')),
    status          text NOT NULL CHECK (status IN
                        ('HELD', 'CONFIRMED', 'ACTIVE', 'COMPLETED', 'EXPIRED', 'CANCELLED', 'NO_SHOW')),
    -- The reserved time as one value, e.g. [10:00, 11:00). Stored in UTC.
    time_range      tstzrange NOT NULL,
    hold_expires_at timestamptz,                 -- set while HELD (waiting for payment)
    otp_hash        text,                        -- HMAC of the 6-digit code, never the code
    otp_used_at     timestamptz,
    booking_fee     money_inr NOT NULL DEFAULT 0,
    refund_amount   money_inr NOT NULL DEFAULT 0,
    cancelled_at    timestamptz,
    cancel_reason   text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    -- The range must be a real, finite span written as [start, end): it includes the
    -- start minute and excludes the end minute, so 10:00-10:30 and 10:30-11:00 touch
    -- but do not overlap.
    CONSTRAINT bookings_valid_time_range CHECK (
        NOT isempty(time_range)
        AND NOT lower_inf(time_range) AND NOT upper_inf(time_range)
        AND lower_inc(time_range) AND NOT upper_inc(time_range)
    ),

    -- Every booking belongs to a user, except kiosk walk-ins.
    CONSTRAINT bookings_user_required CHECK (source = 'WALK_IN' OR user_id IS NOT NULL),

    -- THE NO-DOUBLE-BOOKING RULE.
    -- Among bookings that still hold a charger (HELD, CONFIRMED or ACTIVE), no two may
    -- have the same charger_id AND overlapping time ranges (&& means "overlaps").
    -- If two people book the same slot at the same instant, PostgreSQL accepts one and
    -- rejects the other with error 23P01, which the API turns into "slot just taken".
    -- Finished, cancelled, expired and no-show bookings no longer count, so their
    -- time becomes free again.
    CONSTRAINT bookings_no_double_booking EXCLUDE USING gist (
        charger_id WITH =,
        time_range WITH &&
    ) WHERE (status IN ('HELD', 'CONFIRMED', 'ACTIVE'))
);

-- A user may hold only one unpaid slot at a time, so nobody can hoard slots.
CREATE UNIQUE INDEX bookings_one_hold_per_user ON bookings (user_id)
    WHERE status = 'HELD' AND user_id IS NOT NULL;

CREATE INDEX bookings_user_created ON bookings (user_id, created_at DESC);
-- No extra index is needed for "is this charger free at this time?": the exclusion
-- constraint above already builds a GiST index on (charger_id, time_range) for live bookings.

CREATE TRIGGER bookings_set_updated_at BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- History of every status change, written automatically by the trigger below.
-- Useful for support ("what happened to my booking?") and for showing the jury.
CREATE TABLE booking_events (
    event_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    booking_id  uuid NOT NULL REFERENCES bookings (booking_id) ON DELETE CASCADE,
    from_status text,                            -- empty for the first event
    to_status   text NOT NULL,
    actor       text NOT NULL CHECK (actor IN ('USER', 'DEVICE', 'SYSTEM', 'ADMIN')),
    reason      text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX booking_events_booking ON booking_events (booking_id, created_at);


-- THE STATUS RULES, as data. Each row is one allowed move. An empty from_status means
-- "a new booking may start in this status"; an empty source means "for any source".
-- Matches the state diagram in docs/architecture.md section 6.1 and the API's
-- state machine (backend/app/features/bookings/state_machine.py, Phase 4).
CREATE TABLE allowed_booking_transitions (
    from_status text,
    to_status   text NOT NULL,
    source      text CHECK (source IN ('APP', 'INSTANT', 'WALK_IN')),
    description text NOT NULL
);

CREATE UNIQUE INDEX allowed_booking_transitions_unique
    ON allowed_booking_transitions (coalesce(from_status, '*'), to_status, coalesce(source, '*'));

INSERT INTO allowed_booking_transitions (from_status, to_status, source, description) VALUES
    (NULL,        'HELD',      'APP',     'User picks a slot; held while paying the booking fee'),
    (NULL,        'CONFIRMED', 'INSTANT', '"Charge now": no fee, confirmed immediately'),
    (NULL,        'HELD',      'WALK_IN', 'Kiosk walk-in; held while the payment QR is shown'),
    ('HELD',      'CONFIRMED', 'APP',     'Booking fee payment verified; OTP issued'),
    ('HELD',      'ACTIVE',    'WALK_IN', 'Walk-in payment verified; charging starts'),
    ('HELD',      'EXPIRED',   NULL,      'Hold time passed without payment'),
    ('HELD',      'CANCELLED', NULL,      'User backed out before paying'),
    ('CONFIRMED', 'ACTIVE',    NULL,      'Correct OTP entered at the kiosk'),
    ('CONFIRMED', 'NO_SHOW',   NULL,      'No OTP by start + 10 minutes; fee kept'),
    ('CONFIRMED', 'CANCELLED', NULL,      'Cancelled by the user, or by the system when the charger is unavailable'),
    ('ACTIVE',    'COMPLETED', NULL,      'Charging stopped by the user, auto-stop, or prepaid amount used up');


-- Rejects any status change that is not in the table above, and records every legal
-- one in booking_events. It runs AFTER the row is written so the event can reference
-- it; raising an error here still undoes the whole statement.
-- Who made the change and why can be passed per transaction:
--     SELECT set_config('chargespot.actor', 'USER', true),
--            set_config('chargespot.reason', 'Cancelled in app', true);
-- (defaults: actor SYSTEM, no reason).
CREATE OR REPLACE FUNCTION enforce_booking_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    previous_status text := CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.status = OLD.status THEN
        RETURN NULL;   -- not a status change
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM allowed_booking_transitions t
        WHERE t.from_status IS NOT DISTINCT FROM previous_status
          AND t.to_status = NEW.status
          AND (t.source IS NULL OR t.source = NEW.source)
    ) THEN
        RAISE EXCEPTION 'Illegal booking status change: % -> % (source %)',
            coalesce(previous_status, '(new booking)'), NEW.status, NEW.source
            USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO booking_events (booking_id, from_status, to_status, actor, reason)
    VALUES (
        NEW.booking_id,
        previous_status,
        NEW.status,
        coalesce(nullif(current_setting('chargespot.actor', true), ''), 'SYSTEM'),
        nullif(current_setting('chargespot.reason', true), '')
    );
    RETURN NULL;
END;
$$;

CREATE TRIGGER bookings_enforce_transition
    AFTER INSERT OR UPDATE OF status ON bookings
    FOR EACH ROW EXECUTE FUNCTION enforce_booking_transition();
