-- 013: "Something changed" nudges for live screens (Supabase Realtime).
--
-- When a booking, a charger or a charging session changes, a trigger sends a tiny message to
-- the topic  station:<station id>  saying only WHICH station and charger. It carries no booking
-- details, so nothing private can leak through Realtime. The web app reacts by asking the API
-- for fresh data (docs/architecture.md section 11): the API stays the single source of truth.
--
-- Realtime exists only on Supabase. On a plain PostgreSQL (the test database) the trigger finds
-- no realtime.send function and does nothing. A problem with Realtime must never break a booking
-- either, so any error here is swallowed.

CREATE FUNCTION notify_station_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    station uuid;
    charger uuid;
    old_station uuid;
BEGIN
    IF to_regprocedure('realtime.send(jsonb,text,text,boolean)') IS NULL THEN
        RETURN NULL;
    END IF;

    IF TG_TABLE_NAME = 'chargers' THEN
        station := NEW.station_id;
        charger := NEW.charger_id;
    ELSE
        charger := NEW.charger_id;
        SELECT station_id INTO station FROM chargers WHERE charger_id = charger;
        -- a booking moved to another charger of the same station: one nudge is enough, but a move
        -- between stations (not done today) would need both
        IF TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'bookings' AND OLD.charger_id IS DISTINCT FROM NEW.charger_id THEN
            SELECT station_id INTO old_station FROM chargers WHERE charger_id = OLD.charger_id;
        END IF;
    END IF;

    IF station IS NOT NULL THEN
        PERFORM realtime.send(
            jsonb_build_object('station_id', station, 'charger_id', charger),
            'changed', 'station:' || station, false
        );
    END IF;
    IF old_station IS NOT NULL AND old_station IS DISTINCT FROM station THEN
        PERFORM realtime.send(
            jsonb_build_object('station_id', old_station, 'charger_id', OLD.charger_id),
            'changed', 'station:' || old_station, false
        );
    END IF;
    RETURN NULL;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

CREATE TRIGGER bookings_notify AFTER INSERT OR UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION notify_station_change();
CREATE TRIGGER chargers_notify AFTER INSERT OR UPDATE ON chargers
    FOR EACH ROW EXECUTE FUNCTION notify_station_change();
CREATE TRIGGER charging_sessions_notify AFTER INSERT OR UPDATE ON charging_sessions
    FOR EACH ROW EXECUTE FUNCTION notify_station_change();
