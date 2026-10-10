-- 009: Lock every table against direct browser access.
--
-- Supabase automatically exposes tables in the "public" schema through a REST API that
-- anyone holding the project's public "anon" key can call. ChargeSpot never uses that
-- API: all reads and writes go through our own backend. Turning on row-level security
-- with NO policies means those public roles can read and write nothing.
--
-- Our backend connects as the tables' owner, which row-level security does not apply
-- to, so it keeps full access.
--
-- Any table added by a later migration must enable row-level security too; a test
-- (database/tests/test_schema.py) fails if one is missed.

DO $$
DECLARE
    t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    END LOOP;
END;
$$;
