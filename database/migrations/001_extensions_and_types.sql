-- 001: Extensions and shared building blocks used by every later migration.

-- btree_gist lets a GiST index compare ordinary values (like a charger's ID) with "=".
-- The no-double-booking rule in 004 needs it to combine "same charger" AND
-- "overlapping time range" in one exclusion constraint.
-- Supabase keeps extensions in their own schema; we create it so local PostgreSQL matches.
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA extensions;

-- Domains are named, reusable column types with a built-in CHECK. Declaring the allowed
-- values once keeps every table consistent. They must match frontend/shared/src/constants.ts.

-- Plug standards used in India.
CREATE DOMAIN connector_type AS text
    CHECK (VALUE IN ('CCS2', 'TYPE2', 'CHADEMO', 'BHARAT_AC001', 'BHARAT_DC001', 'TYPE1', 'OTHER'));

-- Where a row's data came from. 'synthetic' rows are generated and shown with an
-- "approximate data" badge; 'manual' rows were entered or verified by a person.
CREATE DOMAIN data_source AS text
    CHECK (VALUE IN ('ocm', 'osm', 'synthetic', 'manual'));

-- Money in Indian rupees, never negative.
CREATE DOMAIN money_inr AS numeric(10, 2)
    CHECK (VALUE >= 0);

-- Keeps every table's updated_at column current without relying on application code.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
