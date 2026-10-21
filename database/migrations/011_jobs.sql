-- 011: Background jobs, charger events and the charging energy formula.
--
-- Everything here is a plain SQL function, so tests can call it directly, pretending it is any
-- moment: every job takes `p_now timestamptz DEFAULT now()`. pg_cron runs them every minute
-- (012) and the API runs the same functions "lazily" before it answers, so what people see is
-- right even when a job has not run yet (docs/architecture.md sections 6.2 and 10).
-- Jobs change a booking's status only through the legal moves the trigger in 004 allows, with
-- the actor SYSTEM.

-- ---------------------------------------------------------------- rules the jobs read

-- The same numbers as BOOKING_RULES / CHARGING_RULES in backend/app/config.py. A test checks
-- that the two copies agree, so a rule cannot be changed in only one place.
CREATE TABLE job_rules (
    name        text PRIMARY KEY,
    value       numeric NOT NULL,
    description text NOT NULL
);
ALTER TABLE job_rules ENABLE ROW LEVEL SECURITY;

INSERT INTO job_rules (name, value, description) VALUES
    ('reservation_lock_before_start', 15,  'Minutes before a booking starts that its charger is reserved (outside starts are refused)'),
    ('no_show_after_start',           10,  'Minutes after the start with no code entered before a booking becomes NO_SHOW'),
    ('buffer_before_next_booking',     5,  'Minutes before the next booking that a walk-in session is stopped'),
    ('charging_efficiency',            0.9, 'Share of the charger''s rated power that reaches the battery'),
    ('default_start_soc_percent',     20,  'Battery level assumed at the start of a session when it is not known'),
    ('default_battery_kwh',           40,  'Battery size assumed when the booking has no vehicle');

CREATE FUNCTION job_rule(p_name text) RETURNS numeric
LANGUAGE sql STABLE AS $$ SELECT value FROM job_rules WHERE name = p_name $$;

-- ---------------------------------------------------------------- what happened to a booking

-- Set when the charger's situation changes a booking: it was moved to another charger, the
-- driver was warned that the charger is busy, or it was cancelled because no charger was free.
ALTER TABLE bookings
    ADD COLUMN moved_from_charger_id uuid REFERENCES chargers (charger_id) ON DELETE SET NULL,
    ADD COLUMN notice_kind text CHECK (notice_kind IN ('WARNING', 'MOVED', 'CANCELLED_NO_CHARGER')),
    ADD COLUMN notice_text text;

-- Partial indexes so each job finds its few rows without scanning every booking.
CREATE INDEX bookings_held_expiry ON bookings (hold_expires_at) WHERE status = 'HELD';
CREATE INDEX bookings_confirmed_start ON bookings ((lower(time_range))) WHERE status = 'CONFIRMED';
CREATE INDEX bookings_active_charger ON bookings (charger_id) WHERE status = 'ACTIVE';

-- ---------------------------------------------------------------- the energy formula

-- Energy delivered = power x hours x efficiency, but never more than the battery can still take:
--   battery size x (100% - the level it started at).
-- backend/app/features/charging/energy.py is the same formula in Python; a test makes them agree.
CREATE FUNCTION session_energy_kwh(
    p_power_kw numeric, p_started_at timestamptz, p_until timestamptz,
    p_battery_kwh numeric DEFAULT NULL, p_start_soc numeric DEFAULT NULL
) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT round(
        least(
            -- multiply first and divide once at the end, so a result that is exactly half a unit rounds the same way everywhere
            coalesce(p_power_kw, 0) * greatest(extract(epoch FROM (p_until - p_started_at)), 0) * job_rule('charging_efficiency') / 3600.0,
            coalesce(p_battery_kwh, job_rule('default_battery_kwh')) * (100 - coalesce(p_start_soc, job_rule('default_start_soc_percent'))) / 100.0
        ),
        3
    )
$$;

-- The bill: energy x the charger's price per kWh, in rupees to 2 decimals.
CREATE FUNCTION session_bill_amount(p_energy_kwh numeric, p_price_per_kwh numeric) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$ SELECT round(p_energy_kwh * coalesce(p_price_per_kwh, 0), 2) $$;

-- ---------------------------------------------------------------- charger events

-- True while a charger is reserved for a confirmed booking: from 15 minutes before its start
-- until it ends (or is marked no-show, cancelled or started, which stop it being CONFIRMED).
CREATE FUNCTION charger_is_locked(p_charger uuid, p_now timestamptz DEFAULT now()) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.charger_id = p_charger AND b.status = 'CONFIRMED'
          AND lower(b.time_range) <= p_now + make_interval(mins => job_rule('reservation_lock_before_start')::int)
          AND p_now < upper(b.time_range)
    )
$$;

-- A charger's physical status changes ONLY through events like these, in the style of the
-- OCPP protocol real chargers speak, and every event is logged in charger_events.
-- Returns the new status, or 'REJECTED' when the charger refuses (a reserved charger refuses an
-- outside start, just as a real one would).
CREATE FUNCTION apply_charger_event(
    p_charger uuid, p_event text, p_details jsonb DEFAULT '{}', p_source text DEFAULT 'SIMULATOR',
    p_now timestamptz DEFAULT now()
) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    current_status text;
    next_status text;
    locked boolean;
BEGIN
    SELECT status INTO current_status FROM chargers WHERE charger_id = p_charger FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown charger %', p_charger USING ERRCODE = 'no_data_found';
    END IF;
    locked := charger_is_locked(p_charger, p_now);

    next_status := CASE
        WHEN p_event = 'RESERVE'        AND current_status = 'AVAILABLE' THEN 'RESERVED'
        WHEN p_event = 'RELEASE'        AND current_status = 'RESERVED' THEN 'AVAILABLE'
        WHEN p_event = 'SESSION_START'  AND current_status IN ('AVAILABLE', 'RESERVED') THEN 'CHARGING'
        WHEN p_event = 'EXTERNAL_START' AND current_status = 'AVAILABLE' AND NOT locked THEN 'CHARGING'
        WHEN p_event IN ('SESSION_STOP', 'EXTERNAL_STOP', 'UNPLUG') AND current_status = 'CHARGING'
            THEN CASE WHEN locked THEN 'RESERVED' ELSE 'AVAILABLE' END
        WHEN p_event = 'FAULT'          AND current_status IN ('AVAILABLE', 'RESERVED', 'CHARGING') THEN 'FAULTED'
        WHEN p_event = 'RECOVER'        AND current_status = 'FAULTED'
            THEN CASE WHEN locked THEN 'RESERVED' ELSE 'AVAILABLE' END
        ELSE NULL
    END;

    IF next_status IS NULL THEN
        INSERT INTO charger_events (charger_id, event, source, details, created_at)
        VALUES (p_charger, 'REJECTED_' || p_event, p_source,
                p_details || jsonb_build_object('status', current_status, 'reserved', locked), p_now);
        RETURN 'REJECTED';
    END IF;

    UPDATE chargers SET status = next_status WHERE charger_id = p_charger AND status <> next_status;
    INSERT INTO charger_events (charger_id, event, source, details, created_at)
    VALUES (p_charger, p_event, p_source, p_details || jsonb_build_object('from', current_status, 'to', next_status), p_now);
    RETURN next_status;
END;
$$;

-- ---------------------------------------------------------------- ending a session

-- Ends a charging session at `p_ended_at`: works out the energy and the bill, completes the
-- booking and frees the charger. Safe to call twice (the second call changes nothing).
-- App and instant sessions are billed (DUE until paid); walk-in sessions were prepaid; outside
-- sessions are not ours to bill.
CREATE FUNCTION finish_session(
    p_session uuid, p_ended_at timestamptz, p_reason text, p_actor text DEFAULT 'SYSTEM',
    p_now timestamptz DEFAULT now()
) RETURNS charging_sessions
LANGUAGE plpgsql AS $$
DECLARE
    s charging_sessions%ROWTYPE;
    ch chargers%ROWTYPE;
    battery numeric;
    energy numeric;
    bill numeric;
    ended timestamptz;
BEGIN
    SELECT * INTO s FROM charging_sessions WHERE session_id = p_session FOR UPDATE;
    IF NOT FOUND OR s.ended_at IS NOT NULL THEN
        RETURN s;
    END IF;
    SELECT * INTO ch FROM chargers WHERE charger_id = s.charger_id;
    SELECT v.battery_kwh INTO battery
    FROM bookings b JOIN vehicles v ON v.vehicle_id = b.vehicle_id WHERE b.booking_id = s.booking_id;

    ended := greatest(p_ended_at, s.started_at);
    energy := session_energy_kwh(ch.power_kw, s.started_at, ended, battery, s.start_soc_percent);
    bill := CASE WHEN s.source = 'EXTERNAL' THEN NULL ELSE session_bill_amount(energy, ch.price_per_kwh) END;

    UPDATE charging_sessions SET
        ended_at = ended,
        end_reason = p_reason,
        energy_kwh = energy,
        bill_amount = bill,
        bill_status = CASE
            WHEN s.source = 'EXTERNAL' THEN NULL
            WHEN s.source = 'WALK_IN' THEN 'PREPAID_SETTLED'
            WHEN bill = 0 THEN 'PAID'
            ELSE 'DUE'
        END,
        paid_at = CASE WHEN s.source = 'BOOKING' AND bill = 0 THEN p_now ELSE paid_at END
    WHERE session_id = p_session
    RETURNING * INTO s;

    IF s.booking_id IS NOT NULL THEN
        PERFORM set_config('chargespot.actor', p_actor, true), set_config('chargespot.reason', 'Charging ended: ' || p_reason, true);
        UPDATE bookings SET status = 'COMPLETED' WHERE booking_id = s.booking_id AND status = 'ACTIVE';
    END IF;

    PERFORM apply_charger_event(
        s.charger_id, CASE WHEN s.source = 'EXTERNAL' THEN 'EXTERNAL_STOP' ELSE 'SESSION_STOP' END,
        jsonb_build_object('session_id', s.session_id, 'reason', p_reason), 'SYSTEM', p_now
    );
    RETURN s;
END;
$$;

-- ---------------------------------------------------------------- the simulator

-- What the admin's "simulate" button (and the demo command line) calls. Returns what happened.
--   EXTERNAL_START  someone starts the charger with the operator's own app or card
--   EXTERNAL_STOP   that outside session ends
--   UNPLUG          whatever is charging is unplugged (ends the session, bill up to now)
--   FAULT / RECOVER the charger breaks / is repaired
CREATE FUNCTION simulate_charger_event(p_charger uuid, p_event text, p_now timestamptz DEFAULT now()) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    result text;
    status_now text;
    new_session uuid;
    running charging_sessions%ROWTYPE;
BEGIN
    IF p_event NOT IN ('EXTERNAL_START', 'EXTERNAL_STOP', 'FAULT', 'RECOVER', 'UNPLUG') THEN
        RAISE EXCEPTION 'Unknown event %', p_event USING ERRCODE = 'invalid_parameter_value';
    END IF;
    PERFORM 1 FROM chargers WHERE charger_id = p_charger FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown charger %', p_charger USING ERRCODE = 'no_data_found';
    END IF;
    SELECT * INTO running FROM charging_sessions WHERE charger_id = p_charger AND ended_at IS NULL;

    IF p_event = 'EXTERNAL_START' THEN
        result := apply_charger_event(p_charger, 'EXTERNAL_START', '{}', 'SIMULATOR', p_now);
        IF result = 'REJECTED' THEN
            SELECT status INTO status_now FROM chargers WHERE charger_id = p_charger;
            RETURN jsonb_build_object(
                'accepted', false, 'status', status_now,
                'reason', CASE
                    WHEN status_now = 'RESERVED' OR charger_is_locked(p_charger, p_now)
                        THEN 'The charger is reserved for a booking and refused the start.'
                    WHEN status_now = 'CHARGING' THEN 'The charger is already charging.'
                    ELSE 'The charger is not available (' || status_now || ').'
                END);
        END IF;
        INSERT INTO charging_sessions (charger_id, source, started_at)
        VALUES (p_charger, 'EXTERNAL', p_now) RETURNING session_id INTO new_session;
        RETURN jsonb_build_object('accepted', true, 'status', result, 'session_id', new_session);
    END IF;

    IF p_event = 'EXTERNAL_STOP' THEN
        IF running.session_id IS NULL OR running.source <> 'EXTERNAL' THEN
            RETURN jsonb_build_object('accepted', false, 'status', (SELECT status FROM chargers WHERE charger_id = p_charger),
                                      'reason', 'No outside session is running on this charger.');
        END IF;
        PERFORM finish_session(running.session_id, p_now, 'USER_STOP', 'SYSTEM', p_now);
    ELSIF p_event = 'UNPLUG' THEN
        IF running.session_id IS NULL THEN
            RETURN jsonb_build_object('accepted', false, 'status', (SELECT status FROM chargers WHERE charger_id = p_charger),
                                      'reason', 'Nothing is charging on this charger.');
        END IF;
        PERFORM finish_session(running.session_id, p_now, 'UNPLUGGED', 'SYSTEM', p_now);
    ELSIF p_event = 'FAULT' THEN
        IF running.session_id IS NOT NULL THEN
            PERFORM finish_session(running.session_id, p_now, 'ADMIN', 'SYSTEM', p_now);
        END IF;
        PERFORM apply_charger_event(p_charger, 'FAULT', '{}', 'SIMULATOR', p_now);
    ELSE
        PERFORM apply_charger_event(p_charger, 'RECOVER', '{}', 'SIMULATOR', p_now);
    END IF;

    SELECT status INTO status_now FROM chargers WHERE charger_id = p_charger;
    RETURN jsonb_build_object('accepted', true, 'status', status_now);
END;
$$;

-- ---------------------------------------------------------------- the five jobs

-- 1. Unpaid holds whose time ran out become EXPIRED (5 minutes for app bookings, 3 for walk-ins:
--    the deadline is stored on each booking).
CREATE FUNCTION expire_holds(p_now timestamptz DEFAULT now(), p_station uuid DEFAULT NULL) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    r record;
    n integer := 0;
BEGIN
    FOR r IN
        SELECT b.booking_id FROM bookings b JOIN chargers c ON c.charger_id = b.charger_id
        WHERE b.status = 'HELD' AND b.hold_expires_at <= p_now AND (p_station IS NULL OR c.station_id = p_station)
        ORDER BY b.booking_id
        FOR UPDATE OF b SKIP LOCKED
    LOOP
        PERFORM set_config('chargespot.actor', 'SYSTEM', true), set_config('chargespot.reason', 'Hold ran out', true);
        UPDATE bookings SET status = 'EXPIRED' WHERE booking_id = r.booking_id;
        n := n + 1;
    END LOOP;
    RETURN n;
END;
$$;

-- 2. A booking that starts and was not claimed in time becomes NO_SHOW. The fee is kept and the
--    slot is free again (a NO_SHOW booking no longer holds its charger).
CREATE FUNCTION mark_no_shows(p_now timestamptz DEFAULT now(), p_station uuid DEFAULT NULL) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    r record;
    n integer := 0;
BEGIN
    FOR r IN
        SELECT b.booking_id FROM bookings b JOIN chargers c ON c.charger_id = b.charger_id
        WHERE b.status = 'CONFIRMED' AND b.otp_used_at IS NULL
          AND lower(b.time_range) <= p_now - make_interval(mins => job_rule('no_show_after_start')::int)
          AND (p_station IS NULL OR c.station_id = p_station)
        ORDER BY b.booking_id
        FOR UPDATE OF b SKIP LOCKED
    LOOP
        PERFORM set_config('chargespot.actor', 'SYSTEM', true),
                set_config('chargespot.reason', 'No code entered within ' || job_rule('no_show_after_start')::int || ' minutes of the start; fee kept', true);
        UPDATE bookings SET status = 'NO_SHOW' WHERE booking_id = r.booking_id;
        n := n + 1;
    END LOOP;
    RETURN n;
END;
$$;

-- 3. The start time has come and the driver's charger is occupied by an outside session (or is
--    broken): move the booking to another free charger with the same plug at the same station,
--    or, if there is none, cancel it with a FULL refund. The driver is never penalised.
CREATE FUNCTION resolve_occupied_starts(p_now timestamptz DEFAULT now(), p_station uuid DEFAULT NULL) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    r record;
    replacement record;
    paid numeric;
    n integer := 0;
BEGIN
    FOR r IN
        SELECT b.booking_id, b.charger_id, b.time_range, b.booking_fee, c.station_id, c.connector_type,
               c.label AS old_label, c.power_kw AS old_power
        FROM bookings b JOIN chargers c ON c.charger_id = b.charger_id
        WHERE b.status = 'CONFIRMED' AND b.otp_used_at IS NULL
          AND lower(b.time_range) <= p_now AND p_now < upper(b.time_range)
          AND (c.status IN ('FAULTED', 'OUT_OF_SERVICE')
               OR EXISTS (SELECT 1 FROM charging_sessions s
                          WHERE s.charger_id = c.charger_id AND s.ended_at IS NULL AND s.source = 'EXTERNAL'))
          AND (p_station IS NULL OR c.station_id = p_station)
        ORDER BY lower(b.time_range), b.booking_id
        FOR UPDATE OF b SKIP LOCKED
    LOOP
        -- A free charger here with the same plug: working, not charging, and with no other live
        -- booking (or unexpired hold) anywhere in this booking's time. The closest power wins.
        SELECT c2.charger_id, c2.label INTO replacement
        FROM chargers c2
        WHERE c2.station_id = r.station_id AND c2.charger_id <> r.charger_id
          AND c2.connector_type = r.connector_type AND c2.status = 'AVAILABLE'
          AND NOT EXISTS (SELECT 1 FROM bookings o
                          WHERE o.charger_id = c2.charger_id AND o.time_range && r.time_range
                            AND (o.status IN ('CONFIRMED', 'ACTIVE') OR (o.status = 'HELD' AND o.hold_expires_at > p_now)))
          AND NOT EXISTS (SELECT 1 FROM charging_sessions s WHERE s.charger_id = c2.charger_id AND s.ended_at IS NULL)
        ORDER BY abs(coalesce(c2.power_kw, 0) - coalesce(r.old_power, 0)), c2.label
        LIMIT 1;

        IF replacement.charger_id IS NOT NULL THEN
            UPDATE bookings SET
                charger_id = replacement.charger_id,
                moved_from_charger_id = r.charger_id,
                notice_kind = 'MOVED',
                notice_text = 'Moved from ' || r.old_label || ' to ' || replacement.label || ', same time.'
            WHERE booking_id = r.booking_id;
            INSERT INTO booking_events (booking_id, from_status, to_status, actor, reason)
            VALUES (r.booking_id, 'CONFIRMED', 'CONFIRMED', 'SYSTEM',
                    'Charger ' || r.old_label || ' was occupied at the start time; moved to ' || replacement.label);
        ELSE
            -- a FULL refund of whatever was actually paid for this booking
            SELECT coalesce(sum(amount - refunded_amount), 0) INTO paid FROM payments
            WHERE booking_id = r.booking_id AND purpose = 'BOOKING_FEE' AND status IN ('CAPTURED', 'PARTIALLY_REFUNDED');
            PERFORM set_config('chargespot.actor', 'SYSTEM', true),
                    set_config('chargespot.reason', 'Charger occupied at the start time and no other charger was free; full refund', true);
            UPDATE bookings SET
                status = 'CANCELLED',
                cancelled_at = p_now,
                cancel_reason = 'The charger was occupied at your start time and no other charger was free, so the booking was cancelled with a full refund.',
                refund_amount = paid,
                notice_kind = 'CANCELLED_NO_CHARGER',
                notice_text = CASE WHEN paid > 0
                    THEN 'Cancelled: the charger was occupied and no other was free. Your booking fee is refunded in full.'
                    ELSE 'Cancelled: the charger was occupied and no other was free.' END
            WHERE booking_id = r.booking_id;
            UPDATE payments SET refunded_amount = amount, status = 'REFUNDED'
            WHERE booking_id = r.booking_id AND purpose = 'BOOKING_FEE' AND status IN ('CAPTURED', 'PARTIALLY_REFUNDED');
        END IF;
        n := n + 1;
    END LOOP;
    RETURN n;
END;
$$;

-- 4. Stops sessions that must end, and bills them.
--    * app and instant sessions end when their booked slot ends;
--    * walk-in sessions end 5 minutes before the next booking on the charger, or when the
--      prepaid amount is used up.
--    Outside (EXTERNAL) sessions are not ours to stop: they end by an EXTERNAL_STOP or UNPLUG event.
CREATE FUNCTION auto_stop_sessions(p_now timestamptz DEFAULT now(), p_station uuid DEFAULT NULL) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    r record;
    stop_at timestamptz;
    stop_reason text;
    next_start timestamptz;
    n integer := 0;
BEGIN
    FOR r IN
        SELECT s.session_id, s.charger_id, s.source, s.started_at, s.start_soc_percent, s.prepaid_amount,
               b.time_range, ch.power_kw, ch.price_per_kwh, v.battery_kwh
        FROM charging_sessions s
        JOIN chargers ch ON ch.charger_id = s.charger_id
        LEFT JOIN bookings b ON b.booking_id = s.booking_id
        LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id
        WHERE s.ended_at IS NULL AND s.source <> 'EXTERNAL' AND (p_station IS NULL OR ch.station_id = p_station)
        ORDER BY s.session_id
        FOR UPDATE OF s SKIP LOCKED
    LOOP
        stop_at := NULL;
        stop_reason := NULL;
        IF r.source = 'BOOKING' THEN
            IF r.time_range IS NOT NULL AND p_now >= upper(r.time_range) THEN
                stop_at := upper(r.time_range);
                stop_reason := 'SLOT_END_AUTO_STOP';
            END IF;
        ELSIF r.source = 'WALK_IN' THEN
            SELECT min(lower(o.time_range)) INTO next_start
            FROM bookings o
            WHERE o.charger_id = r.charger_id AND o.status = 'CONFIRMED' AND lower(o.time_range) > r.started_at;
            IF next_start IS NOT NULL AND p_now >= next_start - make_interval(mins => job_rule('buffer_before_next_booking')::int) THEN
                stop_at := next_start - make_interval(mins => job_rule('buffer_before_next_booking')::int);
                stop_reason := 'NEXT_BOOKING_AUTO_STOP';
            ELSIF r.prepaid_amount IS NOT NULL AND session_bill_amount(
                      session_energy_kwh(r.power_kw, r.started_at, p_now, r.battery_kwh, r.start_soc_percent), r.price_per_kwh
                  ) >= r.prepaid_amount THEN
                stop_at := p_now;
                stop_reason := 'PREPAID_USED';
            END IF;
        END IF;

        IF stop_at IS NOT NULL THEN
            PERFORM finish_session(r.session_id, stop_at, stop_reason, 'SYSTEM', p_now);
            n := n + 1;
        END IF;
    END LOOP;
    RETURN n;
END;
$$;

-- 5. Reserves chargers whose booking starts within 15 minutes (they then refuse outside starts)
--    and releases chargers that no longer need a reservation. If an outside session is still
--    running when the lock time comes, the booked driver gets a warning; it is cleared once the
--    charger is free again.
CREATE FUNCTION apply_reservation_locks(p_now timestamptz DEFAULT now(), p_station uuid DEFAULT NULL) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    r record;
    n integer := 0;
BEGIN
    -- reserve
    FOR r IN
        SELECT DISTINCT c.charger_id FROM chargers c
        WHERE c.status = 'AVAILABLE' AND charger_is_locked(c.charger_id, p_now) AND (p_station IS NULL OR c.station_id = p_station)
    LOOP
        PERFORM apply_charger_event(r.charger_id, 'RESERVE', '{}', 'SYSTEM', p_now);
        n := n + 1;
    END LOOP;

    -- release
    FOR r IN
        SELECT c.charger_id FROM chargers c
        WHERE c.status = 'RESERVED' AND NOT charger_is_locked(c.charger_id, p_now) AND (p_station IS NULL OR c.station_id = p_station)
    LOOP
        PERFORM apply_charger_event(r.charger_id, 'RELEASE', '{}', 'SYSTEM', p_now);
        n := n + 1;
    END LOOP;

    -- warn drivers whose charger is busy with an outside session as the lock time arrives
    UPDATE bookings b SET
        notice_kind = 'WARNING',
        notice_text = 'Another driver is still charging here. We will check again at your start time and move you to a free charger if needed.'
    FROM chargers c
    WHERE c.charger_id = b.charger_id AND b.status = 'CONFIRMED' AND b.notice_kind IS NULL
      AND lower(b.time_range) <= p_now + make_interval(mins => job_rule('reservation_lock_before_start')::int)
      AND p_now < upper(b.time_range)
      AND (p_station IS NULL OR c.station_id = p_station)
      AND EXISTS (SELECT 1 FROM charging_sessions s WHERE s.charger_id = c.charger_id AND s.ended_at IS NULL AND s.source = 'EXTERNAL');

    -- clear the warning once nothing is occupying the charger
    UPDATE bookings b SET notice_kind = NULL, notice_text = NULL
    FROM chargers c
    WHERE c.charger_id = b.charger_id AND b.notice_kind = 'WARNING' AND (p_station IS NULL OR c.station_id = p_station)
      AND NOT EXISTS (SELECT 1 FROM charging_sessions s WHERE s.charger_id = c.charger_id AND s.ended_at IS NULL AND s.source = 'EXTERNAL');

    RETURN n;
END;
$$;

-- All five, in the order that gives the right answer, in ONE call. pg_cron calls this every
-- minute, and the API calls it (for one station) before it answers.
CREATE FUNCTION run_due_jobs(p_now timestamptz DEFAULT now(), p_station uuid DEFAULT NULL) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    expired integer;
    moved_or_cancelled integer;
    no_shows integer;
    stopped integer;
    locks integer;
BEGIN
    expired := expire_holds(p_now, p_station);
    moved_or_cancelled := resolve_occupied_starts(p_now, p_station);
    no_shows := mark_no_shows(p_now, p_station);
    stopped := auto_stop_sessions(p_now, p_station);
    locks := apply_reservation_locks(p_now, p_station);
    RETURN jsonb_build_object(
        'expire_holds', expired, 'resolve_occupied_starts', moved_or_cancelled,
        'mark_no_shows', no_shows, 'auto_stop_sessions', stopped, 'apply_reservation_locks', locks
    );
END;
$$;
