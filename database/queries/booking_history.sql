-- Full status history of one booking: every change, who made it and why.
-- Written automatically by the database trigger in migration 004, so it cannot be skipped.
-- Replace the booking ID below, or remove the WHERE line to see the latest changes overall.

SELECT
    e.created_at AT TIME ZONE 'Asia/Kolkata' AS at_ist,
    coalesce(e.from_status, '(created)')      AS from_status,
    e.to_status,
    e.actor,
    e.reason
FROM booking_events e
WHERE e.booking_id = '00000000-0000-0000-0000-000000000000'
ORDER BY e.event_id;
