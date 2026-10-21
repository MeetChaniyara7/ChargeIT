-- Are the background jobs running, and what have they done? (Supabase, Phase 5)
-- Run each statement on its own in DBeaver.

-- 1. The schedule: one entry that runs all five jobs every minute.
SELECT jobid, jobname, schedule, command, active FROM cron.job;

-- 2. The last runs: status 'succeeded' every minute means the system is running itself.
SELECT status, return_message, start_time AT TIME ZONE 'Asia/Kolkata' AS started_ist
FROM cron.job_run_details ORDER BY start_time DESC LIMIT 10;

-- 3. Run all the jobs right now and see how many rows each one changed.
SELECT run_due_jobs();

-- 4. Where bookings stand.
SELECT status, count(*) FROM bookings GROUP BY status ORDER BY status;

-- 5. Chargers right now (RESERVED = a booking starts within 15 minutes, CHARGING = in use).
SELECT status, count(*) FROM chargers GROUP BY status ORDER BY status;

-- 6. The latest charger events: reservations, outside starts (and refusals), stops, faults.
SELECT e.created_at AT TIME ZONE 'Asia/Kolkata' AS at_ist, s.name AS station, c.label, e.event, e.source, e.details
FROM charger_events e JOIN chargers c USING (charger_id) JOIN stations s USING (station_id)
ORDER BY e.event_id DESC LIMIT 25;

-- 7. Bookings the jobs changed because of the charger (moved, warned, cancelled with a refund).
SELECT b.booking_id, b.status, b.notice_kind, b.notice_text, b.refund_amount
FROM bookings b WHERE b.notice_kind IS NOT NULL ORDER BY b.updated_at DESC LIMIT 25;

-- 8. Sessions running now, and unpaid bills.
SELECT session_id, source, started_at AT TIME ZONE 'Asia/Kolkata' AS started_ist FROM charging_sessions WHERE ended_at IS NULL;
SELECT session_id, bill_amount, ended_at AT TIME ZONE 'Asia/Kolkata' AS ended_ist FROM charging_sessions WHERE bill_status = 'DUE';
