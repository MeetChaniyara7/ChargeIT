# Technical decisions

Choices visible in the codebase, with the reasoning. **"Documented"** means the reason is written in `docs/architecture.md`, `docs/phases.md`, `docs/data.md` or a code comment (the source is named). **"Inferred"** means the code makes the choice clear but the reason is my reading. **"Reason: to be confirmed by me"** means I could not tell.

## Stack

| # | Decision | Reason |
|---|---|---|
| 1 | **FastAPI (Python)** for the API, kept from the original project | Documented (`architecture.md` §2): working Google sign-in already built on it; Python suits the import and scoring scripts; automatic `/docs`; easy concurrency tests with pytest. |
| 2 | **React 19 + Vite + TypeScript + Tailwind CSS v4** for the web app | Documented (§2): existing, working app extended rather than rewritten. Why Tailwind v4 specifically: Reason: to be confirmed by me. |
| 3 | **PostgreSQL on Supabase** | Documented (§2): `btree_gist` makes "no double booking" a database rule, `pg_cron` runs jobs, Realtime pushes updates, and the free tier costs nothing. |
| 4 | **Numbered plain `.sql` migrations + a small Python runner** (`database/migrate.py`) instead of Alembic or `create_all()` | Documented (§2): easy to read, the booking constraint must be raw SQL anyway, and `create_all()` could never change existing tables. |
| 5 | **SQLAlchemy 2.x models that mirror the schema and never create tables** | Documented (`CLAUDE.md`, `database/README.md`): the migration files are the single source of truth. |
| 6 | **Synchronous SQLAlchemy sessions and `def` endpoints** with **psycopg 3** | Reason: to be confirmed by me. (Only the Google redirect callback is `async`.) |
| 7 | **Own JWT (HS256, PyJWT)**, not Supabase Auth | Documented (§3): Google sign-in and JWT already worked and were kept; Supabase's auth client was removed and its JS client kept only for Realtime. |
| 8 | **bcrypt** for passwords | Reason: to be confirmed by me. (Kept from the original code; **TODO: confirm with me**.) |
| 9 | **npm workspaces monorepo**; `@chargespot/shared` consumed as TypeScript source with no build step | Inferred: two front ends (web, planned kiosk) share constants, formatters and API types without a publishing step. |
| 10 | **TypeScript API types generated from the OpenAPI spec** (`openapi-typescript`, run with `npx`) | Documented (§2): the apps always match the API without hand-copying types. |
| 11 | **oxlint** for linting | Reason: to be confirmed by me. |
| 12 | **Front-end unit tests with Node's built-in test runner** (`node --test`), no vitest | Inferred: the project rule is "ask before adding any dependency", and `phases.md` 7.3 lists `vitest` as optional ("ask first"). |
| 13 | **Own component library and CSS tokens** (`src/components/ui`, `frontend/shared/src/styles/tokens.css`), no UI kit | Documented in `docs/ui-flow.md` ("Midnight Charge" design direction). Why no UI kit: Reason: to be confirmed by me. |
| 14 | **Leaflet with OpenStreetMap tiles** | Documented (§2): free, no key; CARTO basemaps now need a key. |

## Business rules and where they are enforced

| # | Decision | Reason |
|---|---|---|
| 15 | **The database enforces no-double-booking** (`EXCLUDE USING gist (charger_id WITH =, time_range WITH &&)` on live statuses) and the API turns SQLSTATE `23P01` into `409 SLOT_TAKEN` | Documented (§5.3): a "check then insert" has a gap; the constraint has none. |
| 16 | **Legal booking status changes are a table plus a trigger**, mirrored by `state_machine.py` (a test compares them) | Documented (§6.1): neither the API nor a background job can make an illegal change. |
| 17 | **Deadlock (`40P01`) is retried once** | Documented (§5.3): the retry then gets a clean `23P01`. |
| 18 | **One slot unit: 30 minutes, 1 to 4 per booking; 5-minute payment hold; ₹199 fee; refund tiers 100/75/50/0%** | Documented (§6.2, §6.3), set by the project owner in Phase 0. All numbers live in `BOOKING_RULES` (`backend/app/config.py`). |
| 19 | **Lazy checks plus `pg_cron` jobs**: stale holds, no-shows, auto-stops are also resolved when someone looks | Documented (§6.2, §10): the free Render server sleeps, so timers inside the API would silently stop; correctness must not depend on when the job last ran. |
| 20 | **Jobs are SQL functions taking `p_now`** | Documented (`phases.md` 5.3): tests can pretend it is any moment. One cron entry (`run_due_jobs`) instead of five is recorded in `phases.md` "As built"; the reason is the fixed order of the five jobs (inferred). |
| 21 | **Amounts are calculated only on the server**; a booking is confirmed only after the Razorpay signature is verified (`/verify`) or a verified webhook | Documented (§8, §14). |
| 22 | **Razorpay test mode; refunds are recorded, not sent** | Documented (§8, §16): free, no real money; the SDK `razorpay` was approved. |
| 23 | **One-time codes are HMAC-SHA256 with a server secret** (`OTP_SECRET`), unique among overlapping bookings at a station, shown once | Documented (§14): a plain hash of 6 digits can be cracked in seconds. |
| 24 | **Energy formula identical in Python and SQL** (`energy.py`, `session_energy_kwh`), constants in `job_rules`, both tested equal | Documented (`phases.md` 5.1): jobs need it in SQL, the live page in Python. |
| 25 | **Times stored in UTC, shown in IST; IST is a fixed +05:30 with no time-zone database** | Documented (§2) and in `backend/app/core/slots.py`: India has no daylight saving, and slot boundaries line up in UTC. |
| 26 | **Realtime messages carry only `{station_id, charger_id}`; the web app re-fetches** | Documented (§11): nothing private can leak, the API stays the single source of truth. |
| 27 | **A charger's status changes only through events** (`apply_charger_event`), all logged | Documented (`phases.md` 5.2): mirrors how real OCPP chargers report. |
| 28 | **Row-level security on every table with no policies** | Documented (§5.3, §14): blocks Supabase's public REST API; only the API connects. |
| 29 | **Pure-function modules** (`scoring.py`, `refunds.py`, `energy.py`, `slots.py`, `selection.ts`, `parseSearch`) | Documented for scoring (`phases.md` 3.4); the others follow the same pattern: unit-testable with no database or network. |

## Data and services

| # | Decision | Reason |
|---|---|---|
| 30 | **Import Gujarat first** from Open Charge Map and OpenStreetMap, clean and de-duplicate; keep the 10 hand-verified Ahmedabad stations | Documented (§13, `docs/data.md`). |
| 31 | **Generate missing data and label it** (`data_source`, `estimated_fields`, "Approximate" tag); never show invented numbers | Documented (§13). |
| 32 | **Keep two-wheeler stations but hide them** (`vehicle_category`) | Documented (§13): a future section is possible without re-importing. |
| 33 | **OSRM for drive times, with a straight-line fallback at 25 km/h** | Documented (§12, §16): free; one request per recommendation. |
| 34 | **Nominatim only on Enter, cached in `geocode_cache`, 1 request per second** | Documented (§2, §16): its usage policy forbids search-as-you-type. |
| 35 | **`pg_trgm` for typo-tolerant suggestions, from our own data only** | Documented (`phases.md` 3.10, `architecture.md` §12.2). |
| 36 | **Supabase session pooler connection string** for the API | Documented (§16): direct connections are IPv6-only and Render cannot reach them. |
| 37 | **Filters held in the page URL**, picks in `sessionStorage`, recent searches in `localStorage` | Inferred: shareable views and Back working; browser-only data stays out of the API. |
| 38 | **Everything on free tiers** (Supabase, Render, Vercel, Razorpay test, OSM services) | Documented (§2): a stated project constraint. |

## Decided by the owner (2026-10-21)

- **Local development uses the one Supabase database.** It is free, so no separate dev database. Tests still use a throwaway local database.
- **Nothing is deployed.** The project is in the development phase.
- **The single `chargespot-jobs` cron entry stays** (one schedule runs all five jobs in a fixed order every minute).

## Open questions about decisions

- Why Python 3.12, synchronous SQLAlchemy sessions, bcrypt, oxlint and Tailwind v4 were chosen: not recorded, and the owner does not know. Treat them as inherited defaults.
