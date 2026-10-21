-- 012: Run the background jobs every minute with pg_cron.
--
-- pg_cron runs inside the database around the clock. (The free Render server sleeps when idle,
-- so a timer inside the API would silently stop; see docs/architecture.md section 10.)
--
-- On a database without pg_cron (a plain local PostgreSQL, such as the test database) this file
-- does nothing: the jobs are still ordinary functions, and the API runs them lazily.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        BEGIN
            CREATE EXTENSION pg_cron;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'pg_cron is not available here (%): the jobs are not scheduled.', SQLERRM;
            RETURN;
        END;
    END IF;

    -- One entry runs the five jobs in the right order (run_due_jobs, see 011). Scheduling again
    -- with the same name replaces the old entry, so this file is safe to re-run.
    PERFORM cron.schedule('chargespot-jobs', '* * * * *', 'SELECT run_due_jobs()');
END;
$$;
