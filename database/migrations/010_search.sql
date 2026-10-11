-- 010: Fuzzy text search for the Explore search box.
--
-- pg_trgm compares text by its three-letter pieces ("trigrams"), so a typo such as
-- "tata powr" still finds "Tata Power". It is free and built into Supabase. Like
-- btree_gist (001), it lives in the "extensions" schema, so the API calls its
-- functions as extensions.word_similarity(...).
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;

-- Trigram indexes keep "contains" (ILIKE '%bopal%') and similarity searches fast as the
-- number of stations grows. The suggest endpoint searches station names, cities and
-- operator names (operators live in their own table, see 003).
CREATE INDEX stations_name_trgm ON stations USING gin (name extensions.gin_trgm_ops);
CREATE INDEX stations_city_trgm ON stations USING gin (city extensions.gin_trgm_ops);
CREATE INDEX operators_name_trgm ON operators USING gin (name extensions.gin_trgm_ops);
