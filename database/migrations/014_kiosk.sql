-- 014: The station kiosk (Phase 6): walk-in settlement and admin alerts.
--
-- 1. Walk-ins pay first (a Razorpay payment link shown as a QR). When the session ends, the bill
--    can never be more than the prepaid amount, and what is left over is recorded as a refund on
--    that payment (as the app's booking fee refunds are: recorded, not sent, in test mode).
-- 2. A walk-in session also stops when its booked window ends (the earlier of 2 hours and 5 minutes
--    before the next booking), not only when the money runs out.
-- 3. admin_alerts: somewhere for the system to raise a flag for the admin page (Phase 7). The
--    kiosk raises one when a device sees 20 or more wrong codes in 10 minutes.
--
-- finish_session and auto_stop_sessions are replaced (CREATE OR REPLACE): migration 011 stays as it was applied.

-- ---------------------------------------------------------------- admin alerts

CREATE TABLE admin_alerts (
    alert_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind        text NOT NULL CHECK (kind IN ('KIOSK_OTP_GUESSING')),
    station_id  uuid REFERENCES stations (station_id) ON DELETE CASCADE,
    device_id   uuid REFERENCES station_devices (device_id) ON DELETE SET NULL,
    message     text NOT NULL,
    details     jsonb NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz
);

CREATE INDEX admin_alerts_open ON admin_alerts (created_at DESC) WHERE resolved_at IS NULL;
CREATE INDEX admin_alerts_device ON admin_alerts (device_id, kind, created_at DESC);

ALTER TABLE admin_alerts ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE admin_alerts IS 'Flags raised by the system for the admin to look at (kiosk code guessing today). Phase 7 shows them.';

-- ---------------------------------------------------------------- ending a session (with walk-in settlement)

CREATE OR REPLACE FUNCTION finish_session(
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
    leftover numeric := 0;
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

    -- A walk-in never pays more than they prepaid. The job runs once a minute, so the meter can have run a
    -- little past the money: cut the energy back to what the prepaid amount buys.
    IF s.source = 'WALK_IN' AND s.prepaid_amount IS NOT NULL THEN
        IF bill > s.prepaid_amount THEN
            bill := s.prepaid_amount;
            energy := round(s.prepaid_amount / ch.price_per_kwh, 3);
        END IF;
        leftover := greatest(s.prepaid_amount - bill, 0);
    END IF;

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

    IF s.source = 'WALK_IN' AND leftover > 0 THEN
        UPDATE payments SET
            refunded_amount = leftover,
            status = CASE WHEN leftover >= amount THEN 'REFUNDED' ELSE 'PARTIALLY_REFUNDED' END
        WHERE booking_id = s.booking_id AND purpose = 'WALKIN_PREPAID' AND status = 'CAPTURED';
        UPDATE bookings SET refund_amount = leftover WHERE booking_id = s.booking_id;
    END IF;

    PERFORM apply_charger_event(
        s.charger_id, CASE WHEN s.source = 'EXTERNAL' THEN 'EXTERNAL_STOP' ELSE 'SESSION_STOP' END,
        jsonb_build_object('session_id', s.session_id, 'reason', p_reason), 'SYSTEM', p_now
    );
    RETURN s;
END;
$$;

-- ---------------------------------------------------------------- automatic stops

CREATE OR REPLACE FUNCTION auto_stop_sessions(p_now timestamptz DEFAULT now(), p_station uuid DEFAULT NULL) RETURNS integer
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
            ELSIF r.time_range IS NOT NULL AND p_now >= upper(r.time_range) THEN
                stop_at := upper(r.time_range);
                stop_reason := 'SLOT_END_AUTO_STOP';
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
