-- 015: The admin area (Phase 7).
--
-- 1. A charger can be taken out of service and put back by an admin. Like every other status change this
--    goes through apply_charger_event, so it is logged in charger_events. (A RECOVER still only repairs a
--    FAULTED charger: an out-of-service one needs an explicit RESTORE.)
-- 2. admin_alerts may now also hold WEBHOOK_FAILED (a Razorpay webhook that could not be processed).
-- 3. Admin lists read bookings by date and status and payments by purpose, so give them indexes.
--
-- apply_charger_event is replaced (CREATE OR REPLACE): migration 011 stays as it was applied.

ALTER TABLE admin_alerts DROP CONSTRAINT admin_alerts_kind_check;
ALTER TABLE admin_alerts ADD CONSTRAINT admin_alerts_kind_check CHECK (kind IN ('KIOSK_OTP_GUESSING', 'WEBHOOK_FAILED'));

CREATE INDEX bookings_created ON bookings (created_at DESC);
CREATE INDEX bookings_status_start ON bookings (status, (lower(time_range)));
CREATE INDEX payments_purpose_status ON payments (purpose, status);

CREATE OR REPLACE FUNCTION apply_charger_event(
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
        WHEN p_event = 'OUT_OF_SERVICE' AND current_status IN ('AVAILABLE', 'RESERVED', 'CHARGING', 'FAULTED') THEN 'OUT_OF_SERVICE'
        WHEN p_event = 'RESTORE'        AND current_status = 'OUT_OF_SERVICE'
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
