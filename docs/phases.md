# ChargeSpot: Build Phases

This is the **step-by-step build plan** for ChargeSpot. For every phase it lists the goal, the detailed tasks, how to check it's done, who on the team owns it, and a **ready-to-paste prompt for Claude Code**.

**Read [architecture.md](architecture.md) first.** It explains *what* we are building and *why*. This file explains *in what order* and *how to check each step*.

---

## Contents

- [How to use this plan](#how-to-use-this-plan)
- [Rules for every phase](#rules-for-every-phase)
- [Overview](#overview)
- [Phase 0: Audit and architecture (done)](#phase-0-audit-and-architecture-done)
- [Phase 1: Monorepo restructure and API skeleton](#phase-1-monorepo-restructure-and-api-skeleton)
- [Phase 2: Database, data import and seed](#phase-2-database-data-import-and-seed)
- [Phase 3: Station discovery, availability and recommendations](#phase-3-station-discovery-availability-and-recommendations)
- [Phase 4: Booking flow and payments](#phase-4-booking-flow-and-payments)
- [Phase 5: Background jobs, charger simulator and realtime](#phase-5-background-jobs-charger-simulator-and-realtime)
- [Phase 6: Station kiosk and energy billing](#phase-6-station-kiosk-and-energy-billing)
- [Phase 7: Admin, hardening, docs and deployment](#phase-7-admin-hardening-docs-and-deployment)

---

## How to use this plan

1. **One phase at a time.** Don't start a phase until the previous one has been reviewed and approved.
2. **Start each phase on its own git branch**, e.g. `phase-1-restructure`. Merge into `main` only after the review.
3. **Paste the phase's prompt into Claude Code** from the repository root (`D:\ev2`). Each prompt tells Claude to read this file and `architecture.md`, do only that phase, and stop for review.
4. **Check the "Done when" list yourself** before approving. Run the commands, click through the app.
5. **If something in the plan changes,** update `architecture.md` (the decision) and this file (the tasks) in the same branch, so the docs never drift from the code.

**UI work has its own prompts.** The look and screen flow are agreed in [ui-flow.md](ui-flow.md). [ui-prompts.md](ui-prompts.md) has a UI pass to run before Phase 3, plus a UI prompt to run alongside each of Phases 3–7.

**Prompts work for teammates too.** If one person owns a part of a phase, they can paste the prompt and add *"Only do tasks X.1–X.4"* at the end.

---

## Rules for every phase

These apply to every prompt below. Each prompt reminds Claude Code to follow them.

1. **Scope:** only the current phase's tasks. Note anything else under "Suggestions for later" in the summary.
2. **Don't rewrite working login or navigation.** Move and adapt them, but keep the behaviour.
3. **Ask before** adding any dependency not listed in the phase, or any paid service.
4. **Already approved:** `razorpay` (Python SDK), `pytest`, `openapi-typescript` (run on demand via `npx`, because it requires TypeScript 5 and the project uses 6), `qrcode.react` (kiosk).
5. **Secrets only in `.env`** files. Every app has an up-to-date `.env.example`. Never commit keys or `data/legacy/*.csv`.
6. **Small, clearly named files**, organised by feature (router → service → repository → schemas).
7. **Explain key decisions in short code comments**. The jury reads the code.
8. **Tests:** every rule about bookings, OTPs, payments, jobs and scoring gets a test.
9. **Times:** stored in UTC, shown in Asia/Kolkata. Money shown in ₹ with 2 decimals.
10. **End of phase:** run tests, build and lint. Then reply with: what changed, how to run and test it, anything left undone, and what's next. **Then stop and wait for approval.**

---

## Overview

| Phase | What you get at the end | Effort (person-days) | Main owner |
|---|---|---|---|
| 0 | Audit, decisions, `architecture.md` | done | — |
| 1 | New folder layout, clean API skeleton, secure routes, shared package, ChargeSpot branding | 3–4 | A (with C) |
| 2 | Real schema in Supabase with the no-double-booking rule; Gujarat stations imported and cleaned; synthetic chargers and demo data | 5–6 | B |
| 3 | Map shows real data by area, availability grid, "best station" suggestions, address search | 5–6 | C (with B) |
| 4 | Book a slot, pay ₹199, get an OTP, My Bookings, cancel with refund, "Charge now" | 7–8 | A + C |
| 5 | Holds expire, no-shows, auto-stop, reservation locks, live updates on screen, live charging page | 4–5 | A |
| 6 | Kiosk app: status board, OTP start, walk-in QR payment; energy bill payment in the web app | 6–7 | D (with A) |
| 7 | Admin pages, edge cases, full tests, CI, docs, deployment, jury demo script | 6–8 | everyone |
| | **Total** | **≈ 36–44** (≈ 3–4 weeks for 4 people) | |

**Team roles** (from `architecture.md`):
**A**, backend core · **B**, data and database · **C**, user web app · **D**, kiosk and delivery.

**What can run in parallel:** once Phase 2's migrations are merged, C can build Phase 3–4 UI against mocked API responses while A builds the API. D can build the kiosk UI (Phase 6) with mocked data from Phase 3 onward.

---

## Phase 0: Audit and architecture (done)

- [x] Audited the existing code and data
- [x] Agreed on every product and technical decision
- [x] Wrote `docs/architecture.md`
- [x] Changed the leaked database password; set `JWT_SECRET_KEY` in `backend/.env`

---

## Phase 1: Monorepo restructure and API skeleton

**Goal:** move the existing code into the agreed folder structure, without breaking login, navigation or the map. Make the API secure and well organised, ready to build on.

**Owner:** A (API), C (web app). **Effort:** 3–4 person-days.

### Before starting
- Decide what to do with the **8 uncommitted files** in `backend/` and `frontend/`: commit them first (recommended), or discard them.
- Create the branch `phase-1-restructure`.

### Tasks

**1.1 Repository setup**
- [ ] Root `package.json` with **npm workspaces**: `frontend/user-web`, `frontend/shared` (`frontend/kiosk` is added to the list in Phase 6, when it exists).
- [ ] Root scripts: `dev:web`, `dev:api`, `build`, `lint`, `test:api`.
- [ ] `.gitignore`: add `data/legacy/`, `data/raw/`, `.vite/`, every `.env` except `.env.example`, Python caches, `.venv`.
- [ ] Remove the committed `.vite/` folder from git.
- [ ] Move the exported CSVs into `data/legacy/` (git-ignored). **Never** commit `users.csv`.

**1.2 Restructure the API inside `backend/`**
- [ ] Use `git mv` so history is kept.
- [ ] Create the top-level `database/` folder (with a README explaining `migrations/`, `seeds/`, `imports/`, `queries/`) for Phase 2.
- [ ] Turn it into a proper Python package `app/`, run with `uvicorn app.main:app`. Replace flat imports (`import models`) with package imports.
- [ ] Create `app/features/` with `auth/` and `stations/` for now. Later phases add the others (`admin/` in Phase 7, when it has endpoints; `require_admin` already exists in `auth/dependencies.py`).
- [ ] Move the auth code (`routes/auth.py`, `auth/*.py`) into `app/features/auth/` **with logic unchanged**. Only imports and config access change.

**1.3 Configuration and secrets**
- [ ] `app/config.py`: one place for every setting, read from environment variables.
- [ ] **Fail fast:** the API refuses to start if `DATABASE_URL`, `JWT_SECRET_KEY` or `GOOGLE_CLIENT_ID` is missing. Remove every hard-coded fallback: the DB URL with the old password, the default JWT secret, the Google client ID.
- [ ] `CORS_ORIGINS` and `FRONTEND_URL` come from config. No hard-coded `localhost`.
- [ ] Put the business constants from `architecture.md` section 15 into `config.py` (slot length, fees, windows, refund tiers…). They'll be used in later phases.
- [ ] Update `backend/.env.example` with every variable and a comment for each.

**1.4 Security fixes**
- [ ] **Delete** the unsafe routes: `GET /api/users`, `POST /api/users/sync`, `GET /api/reservations/user/{id}`, `POST /api/reservations`, `GET/POST /api/sessions…`, `GET /api/chargers`, `GET /api/connectors`, `GET /api/operators`. Bookings and sessions are rebuilt properly in Phases 4–6.
- [ ] Keep public read-only `GET /api/stations` and `GET /api/stations/{id}` so the map keeps working.
- [ ] `POST /api/stations` requires an admin. Add a `require_admin` dependency (role `ADMIN`).
- [ ] Google OAuth redirect flow: replace the fixed `state="random_state"` with a random value stored in a short-lived signed cookie and checked on callback.
- [ ] Stop calling `Base.metadata.create_all()` at startup. Phase 2 brings real migrations, and the existing tables already exist.

**1.5 API quality**
- [ ] Replace `print()` and emoji logs with Python `logging`.
- [ ] One error format for all errors: `{"error": {"code": "SLOT_TAKEN", "message": "…"}}`.
- [ ] `GET /health` returns status and app version.
- [ ] API title: **ChargeSpot API**.

**1.6 API tests**
- [ ] `requirements-dev.txt` with `pytest` and `httpx`.
- [ ] Tests: health check; `/auth/me` without a token → 401; a JWT can be created and read back; the app refuses to start without `JWT_SECRET_KEY`; removed routes return 404.

**1.7 Move the web app: `frontend/` → `frontend/user-web/`** (the kiosk joins it as `frontend/kiosk/` in Phase 6)
- [ ] `git mv`, then organise by feature:
  - `src/app/`: `App.tsx`, routes
  - `src/features/auth/`: `AuthContext`, `LoginForm`, `RegisterForm`, `ProtectedRoute`, auth service, types
  - `src/features/stations/`: `Dashboard` (renamed `StationsPage`), `StationMap`, `StationCard`, `SearchBar`
  - `src/features/home/`: `Home`
  - `src/components/layout/`: `Navbar`
  - `src/lib/api.ts`: one `fetch` wrapper that adds the `Authorization` header, parses the error format and handles 401
- [ ] Remove `Header.tsx`, `App.css`, `AgentFloatingButton`, and the Supabase-auth leftovers (`isSupabaseConfigured` and its use in `RegisterForm`). Keep the `@supabase/supabase-js` dependency for Phase 5 realtime.
- [ ] Google client ID only from `VITE_GOOGLE_CLIENT_ID`; remove the hard-coded fallback.
- [ ] Env var `VITE_API_URL` (rename from `VITE_BACKEND_URL`). Remove `VITE_CARTO_API_KEY`: the map uses OpenStreetMap tiles, which need no key.
- [ ] **Behaviour must not change:** login (Google and email), logout, protected dashboard and map all work exactly as before.

**1.8 Shared package: `frontend/shared/`**
- [ ] `src/constants.ts`: booking statuses, booking sources, charger statuses, connector types with display labels, session sources, bill statuses, slot length. These **must match** the database CHECK lists in `architecture.md` 5.2.
- [ ] `src/format.ts`: `formatIST(date)`, `formatINR(amount)`.
- [ ] Script `generate:api-types`: runs `npx openapi-typescript` against the API's `/openapi.json` → `src/api-types.ts`.
- [ ] `user-web` imports from `@chargespot/shared`.

**1.9 Branding: ChargeSpot**
- [ ] Rename VoltPulse → ChargeSpot in the page title, navbar, footer, API title and README.

**1.10 Docs**
- [ ] `docs/setup.md`: prerequisites, install, env files, how to run the API and web app, how to run tests.
- [ ] Update `CLAUDE.md` for the new layout and commands.
- [ ] Short root `README.md` pointing to the docs (the full README comes in Phase 7).

### Done when
- [ ] `npm run dev:web` and `npm run dev:api` both start. Google login, logout and the protected map work as before.
- [ ] The API **refuses to start** without `JWT_SECRET_KEY`.
- [ ] `GET /api/users` returns **404**.
- [ ] No old password, default secret or Google client ID anywhere in the code (`git grep` finds nothing).
- [ ] `npm run build`, `npm run lint` and `pytest` all pass.
- [ ] The UI says ChargeSpot everywhere.

### Prompt for Claude Code
```text
We are building ChargeSpot (a college final-year project). Read docs/architecture.md
and docs/phases.md fully before doing anything. Follow "Rules for every phase" in
docs/phases.md.

Do PHASE 1 only: "Monorepo restructure and API skeleton", tasks 1.1–1.10.

Before moving any file, ask me whether to commit or discard the uncommitted changes
in backend/ and frontend/, then create the branch phase-1-restructure.

Key constraints:
- Use git mv for moves so history is kept.
- Login (Google + email), logout, routing and the station map must behave exactly as
  before. Move and adapt the auth code; do not rewrite its logic.
- Remove every hard-coded secret and fallback (old DB URL, default JWT secret,
  Google client ID). The API must refuse to start without required env vars.
- Delete the unsafe routes listed in task 1.4. Keep public GET /api/stations and
  GET /api/stations/{id}.
- Do not change the database in this phase (no migrations yet) and remove the
  create_all() call.
- Only dependencies already approved in docs/phases.md; ask me before any other.

When finished: run pytest, npm run build and npm run lint; check every item in
"Done when" for Phase 1; then give me a summary (what changed, how to run/test,
anything not done, what's next) and STOP. Wait for my approval before Phase 2.
```

---

## Phase 2: Database, data import and seed

**Goal:** the real database schema on Supabase, with the no-double-booking rule enforced by PostgreSQL. Gujarat stations imported and cleaned, the 10 hand-verified Ahmedabad stations kept, and synthetic chargers and demo bookings so the app looks alive.

**Owner:** B. **Effort:** 5–6 person-days.

### Before starting (you do these)
- [ ] Create a free **Supabase** project, region **Mumbai (ap-south-1)**. Save the database password somewhere safe.
- [ ] Copy the **Session pooler** connection string (Project Settings → Database). Not the direct connection: it's IPv6-only and Render can't reach it.
- [ ] Get a free **Open Charge Map API key** (openchargemap.org → My Profile → API keys).
- [ ] Decide on **two-wheeler-only networks** (Ather Grid, Ola Hypercharger, etc.): exclude them, since ChargeSpot is car-focused (recommended), or keep them?

### Tasks

**2.1 Migration runner**
- [ ] `database/migrate.py`: applies `database/migrations/NNN_name.sql` in order, each in a transaction, and records them in a `schema_migrations` table. `--status` lists applied and pending migrations.
- [ ] Works against Supabase **and** a plain local PostgreSQL (for tests). Migrations that need `pg_cron` skip it cleanly when the extension isn't available.

**2.2 Migrations** (matching `architecture.md` section 5)
- [ ] `001_extensions_and_types.sql`: `btree_gist`; shared domains (`connector_type`, `data_source`, `money_inr`) and the `set_updated_at()` trigger function. (`pg_cron` is added in Phase 5, with the jobs.)
- [ ] `002_users_vehicles.sql`: `users` (keeps today's columns and IDs), `vehicles` (one default per user).
- [ ] `003_stations_chargers.sql`: `operators`, `stations` (with `vehicle_category`, `estimated_fields`), `station_sources` (one row per outside record, keyed by `(data_source, external_ref)`), `chargers`, index on `(latitude, longitude)`, and a `haversine_km()` SQL function.
- [ ] `004_bookings.sql`: `bookings` with the **exclusion constraint**, `[)` range check, one-hold-per-user index, walk-in user rule; `booking_events`; an `allowed_booking_transitions` table and the **trigger** that rejects illegal status changes and writes `booking_events`.
- [ ] `005_station_devices.sql`: `station_devices`, `otp_attempts`.
- [ ] `006_charging.sql`: `charging_sessions`, `charger_events`.
- [ ] `007_payments.sql`: `payments`, `webhook_events`.
- [ ] `008_geocode_cache.sql`: `geocode_cache`.
- [ ] `009_row_level_security.sql`: enable row-level security on **every** table, with no policies.

**2.3 Move existing users across**
- [ ] One-off script `database/imports/migrate_users.py`: copies `users` (IDs, emails, Google IDs, roles) from the old local database to Supabase so existing Google logins keep working. **Skip** the test accounts (`*@example.com`, `ji@gmail.com`).

**2.4 API models**
- [ ] Update the SQLAlchemy models to match the new schema, one `models.py` per feature.
- [ ] Point `backend/.env` at Supabase. `GET /api/stations` must still work (returning the new data).

**2.5 Cleaning helpers: `database/imports/normalize.py`**
- [ ] **Operator names:** an alias table, e.g. `tata`, `TATA`, `Tata power`, `Tata Power EZ Charge` → `Tata Power`. The same for Jio-bp, Ather, Zeon, EESL, ChargeZone, Statiq and Shell.
- [ ] **Connector names** → our list (OCM connection type IDs, OSM `socket:*` tags, and legacy values such as `GB_T` → `BHARAT_DC001`).
- [ ] **Non-car filter:** battery swap (Honda e:swap, Battery Smart, Sun Mobility, "swap"), bike stations (Yulu), phone charging, cycle kiosks, are dropped. Two-wheeler networks and scooter-only plugs are **kept but tagged** `TWO_WHEELER` (decided: car-focused app now, possible two-wheeler section later).
- [ ] Name clean-up: drop junk names like "Unknown Charging Station", using `<operator> – <area>` instead.

**2.6 Import scripts**
- [ ] `database/imports/import_legacy_manual.py`: imports the 10 `VERIFY-ST-*` stations and their chargers from `data/legacy/` as `data_source = manual`.
- [ ] `database/imports/import_osm.py`: Overpass query for `amenity=charging_station` in Gujarat (`ISO3166-2=IN-GJ`). Raw response cached in `data/raw/` (git-ignored). Reads name, operator, `socket:*`, capacity and opening hours.
- [ ] `database/imports/import_ocm.py`: Open Charge Map, `countrycode=IN`, Gujarat bounding box, key from env. Maps connection types and power; `Quantity` → that many chargers.
- [ ] Both importers can be **re-run safely**: each outside record is remembered in `station_sources`, so a re-import updates the existing station (or the station it was merged into) instead of duplicating.
- [ ] The region is a setting (default Gujarat), so other states can be added later.

**2.7 Duplicate removal: `database/imports/dedupe.py`**
- [ ] Stations within **~50 m** with similar names (or one generic name) are merged.
- [ ] Priority: `manual` > `ocm` > `osm`. Chargers from the losing record are merged where they add information.
- [ ] Writes a report of every merge to `data/raw/dedupe_report.csv` so a human can check it.

**2.8 Synthetic data: `database/seeds/` (`profiles.py`, `synthetic.py`, `demo_data.py`) and `database/pipeline.py`, which runs every step in order**
- [ ] For stations with no chargers, or chargers missing power or price: generate realistic chargers based on the operator (e.g. Tata Power: 1–2 × CCS2 30–60 kW at ₹18–22/kWh; malls: Type2 7–22 kW). Tagged `data_source = synthetic`.
- [ ] **Deterministic:** seeded by station ID, so re-running gives the same result.
- [ ] Demo users (one admin), demo vehicles, and **demo bookings for Ahmedabad** over the next 7 days (`CONFIRMED`, plus some `COMPLETED` in the past) so the slot grid looks realistic.
- [ ] Demo kiosk devices for 3 Ahmedabad stations. Their API keys are printed **once** to the console, never stored in plain text.

**2.9 Tests** (against a local PostgreSQL with `btree_gist`)
- [ ] Migrations apply cleanly to an empty database.
- [ ] **Two overlapping live bookings on one charger fail** with error `23P01`.
- [ ] Back-to-back bookings (10:00–10:30 and 10:30–11:00) **are allowed**.
- [ ] A `CANCELLED` or `EXPIRED` booking does not block the slot.
- [ ] A second `HELD` booking for the same user fails.
- [ ] An `APP` booking without a user fails; a `WALK_IN` without a user succeeds.
- [ ] The trigger rejects an illegal change (e.g. `COMPLETED → HELD`) and records legal ones in `booking_events`.
- [ ] Unit tests for operator and connector normalisation, the non-car filter and dedupe.

**2.10 Docs**
- [ ] `docs/setup.md`: Supabase setup, `migrate.py`, import and seed commands, in order.
- [ ] `docs/data.md`: where the data comes from, how it's cleaned, what "synthetic" means, licences and attribution (OSM ODbL, OCM CC BY 4.0).

### Done when
- [ ] `python -m database.pipeline` builds the whole schema and data on a fresh Supabase project.
- [ ] Running the imports, dedupe and seed (in the documented order) gives Gujarat stations with no obvious duplicates and the 10 manual stations intact.
- [ ] The existing map shows the new Gujarat data.
- [ ] You can still sign in with your Google account (users migrated).
- [ ] All Phase 2 tests pass, including the overlap test.

### Prompt for Claude Code
```text
We are building ChargeSpot. Read docs/architecture.md (especially section 5, Data
model, and section 13, Station data strategy) and docs/phases.md before doing
anything. Follow "Rules for every phase".

Do PHASE 2 only: "Database, data import and seed", tasks 2.1–2.10.
Create branch phase-2-database.

Inputs I have prepared:
- Supabase session-pooler URL is in backend/.env as DATABASE_URL.
- The old local database URL is in backend/.env as LEGACY_DATABASE_URL (for the
  one-off user copy in task 2.3).
- OCM_API_KEY is in backend/.env.
- Legacy CSV exports are in data/legacy/.
- Two-wheeler-only networks: <EXCLUDE or KEEP>.

Key constraints:
- Migrations are plain numbered .sql files with comments explaining each constraint
  for the jury. The exclusion constraint, the [) range check, the one-hold-per-user
  index, the walk-in user rule and the status-transition trigger must match
  docs/architecture.md exactly.
- Enable row-level security on every table with no policies.
- Import scripts must be safe to re-run and must never invent data without tagging
  it data_source = 'synthetic'.
- Never import or commit users.csv. Copy users only from the old database via
  task 2.3, skipping test accounts.
- Tests run against a local PostgreSQL (btree_gist); pg_cron is optional there.
- Ask me before adding any dependency (e.g. a fuzzy-matching library; prefer
  Python's difflib).

When finished: run all tests; run the import pipeline end to end and report station
counts per data_source and how many duplicates were merged; check "Done when" for
Phase 2; summarise and STOP. Wait for my approval before Phase 3.
```

---

## Phase 3: Station discovery, availability and recommendations

**Goal:** the map and search use real data efficiently, every station shows a 30-minute availability grid, and the app can suggest the "best station" with a short reason.

**Owner:** C (front end), B (recommendations, availability). **Effort:** 5–6 person-days.

### Tasks

**3.1 Station search API: `app/features/stations/`**
- [ ] `GET /stations?bbox=minLng,minLat,maxLng,maxLat` (for the map) **or** `?lat&lng&radius_km` (for "near me"); optional `connector` filter; result limit.
- [ ] Each station includes a live charger summary: total, free now, connector types, min/max power, min price, and `has_synthetic_data` for the badge.
- [ ] `GET /stations/{id}`: full details and chargers.
- [ ] Replaces the old `/api/stations`. Update the web app to use the new endpoints.

**3.2 Time-slot helpers: `app/core/slots.py`**
- [ ] Turn an IST date into its 30-minute blocks (stored in UTC); round times to block boundaries; check alignment.
- [ ] Tests, including around midnight IST.

**3.3 Availability API: `app/features/availability/`**
- [ ] `GET /stations/{id}/availability?date=YYYY-MM-DD` → for each charger, every 30-minute block of that IST day with a state: `FREE`, `BOOKED`, `HELD`, `PAST`, `OUT_OF_SERVICE`. (`BUSY_EXTERNAL` arrives in Phase 5.)
- [ ] **Lazy check:** expired holds count as free even before the background job runs.
- [ ] One efficient query per request (no query per block).

**3.4 Recommendations: `app/features/recommendations/`**
- [ ] `scoring.py`: **pure functions only**. Normalise each factor (travel time, free compatible chargers, power, price, rating, data quality), apply weights from `config.py`, and build the "why" text.
- [ ] `osrm.py`: **one** OSRM `table` request for the top candidates, with a 3-second timeout; on failure, fall back to straight-line distance at 25 km/h. Results cached briefly.
- [ ] `GET /recommendations?lat&lng&connector&start&duration`: stations within 15 km, top 5 with score and reason, e.g. *"2 CCS2 chargers free · 1.2 km · 60 kW"*.
- [ ] **Unit tests:** ranking order, the effect of changing weights, ties, no candidates, OSRM fallback, the "why" text.

**3.5 Address search: `app/features/geocoding/`**
- [ ] `GET /geocode?q=`: calls Nominatim with a proper User-Agent and `countrycodes=in`, caches results in `geocode_cache`, and respects the 1-request-per-second limit.
- [ ] Called **only on submit**, never while typing (Nominatim's usage policy).

**3.6 Web app: map and list**
- [ ] Split the old dashboard into hooks: `useGeolocation` (**default Ahmedabad** 23.0225, 72.5714), `useStations(bounds)` (re-fetch when the map stops moving, debounced), `useGeocode`.
- [ ] Search bar: on submit, match station names locally first, then geocode the place and move the map there.
- [ ] `StationCard` and map popups: **remove every invented fallback value**, show **₹**, show "unknown" for missing data, show an **"approximate data"** badge when `has_synthetic_data`.
- [ ] OpenStreetMap tiles (darkened with CSS), no key. Footer attribution for OpenStreetMap and Open Charge Map.
- [ ] If the map gets crowded with markers, propose `leaflet.markercluster` (ask before adding).

**3.7 Web app: station page `/stations/:id`**
- [ ] Station details, chargers (connector, power, price, data badge) and a **read-only** availability grid for today and the next 6 days. Booking from the grid comes in Phase 4.
- [ ] "Navigate" button (Google Maps link with coordinates).

**3.8 Web app: "Best stations" panel**
- [ ] Inputs: connector (defaults to the user's vehicle, otherwise chosen), start time, duration (30 min – 2 h).
- [ ] Shows the top 5 with reason text; clicking one opens its station page.

**3.9 Tests**
- [ ] API tests for bbox and radius search, connector filter, and availability with seeded bookings (booked, held, expired-hold, past).

**3.10 Smart search on Explore** (added after the first Phase 3 review; design in [architecture.md](architecture.md) section 12.2)
- [ ] Fix: the search bar was hidden under the map (Leaflet's layers sit at z-index 400–1000). The map's own element now isolates its layers.
- [ ] Migration `010_search.sql`: the `pg_trgm` extension plus trigram indexes on station name, station city and operator name.
- [ ] `parseSearch(text)` in `@chargespot/shared`: pure functions that read plug types, power, "fast", opening hours, price, "near me" and "near/in <place>", and leave unknown words in the text. Tested with Node's built-in test runner (`npm run test:web`).
- [ ] `GET /api/search/suggest?q=&lat=&lng=` (login required): the top 5 stations (by name or address), 3 operators and 3 cities, plus "did you mean". Our database only, with a fixed number of queries.
- [ ] `/api/stations` gains `operator` and `max_price` filters. The page address gains `operator`, `min_kw` and `max_price`.
- [ ] Web: an accessible combobox with "Understood" chips, Stations / Operators / Cities / Places / Recent sections, example searches and quick chips. It fills the screen on phones. Places are looked up on Enter only. "Show without <filter>" appears when the filters leave no stations.

### Done when
- [ ] The search bar is visible over the map on desktop and phone.
- [ ] "fast ccs2 near Bopal" shows CCS2 50 kW+ stations around Bopal, with three "Understood" chips.
- [ ] "tata powr" suggests Tata Power.
- [ ] Typing never calls Nominatim; pressing Enter on a place does, and the result is cached.
- [ ] Filters survive a page refresh and Back; recent searches appear.
- [ ] The map loads stations only for the visible area, starting in Ahmedabad.
- [ ] Searching "Bopal" moves the map to Bopal; searching a station name finds it.
- [ ] No card shows invented numbers; synthetic data shows the badge; prices are in ₹.
- [ ] A station page shows a correct 7-day grid that matches the seeded bookings.
- [ ] "Best stations" returns sensible results with reasons, and still works if OSRM is down.
- [ ] All tests pass.

### Prompt for Claude Code
```text
We are building ChargeSpot. Read docs/architecture.md (sections 6.2, 12, 13 and 16)
and docs/phases.md before doing anything. Follow "Rules for every phase".

Do PHASE 3 only: "Station discovery, availability and recommendations",
tasks 3.1–3.9. Create branch phase-3-discovery.

Key constraints:
- The API decides availability; the front end only displays it.
- Availability must use one efficient query per request and treat expired holds
  as free (lazy check).
- scoring.py must be pure functions (no DB or network) with weights from config.py,
  and must have thorough unit tests.
- OSRM: one table request, 3s timeout, straight-line fallback at 25 km/h.
- Nominatim: only on submit, cached, User-Agent set, countrycodes=in, max 1 req/s.
- Remove every invented fallback value from the UI; show "unknown" or the
  "approximate data" badge instead. Prices in ₹, times in IST.
- Keep login/navigation behaviour unchanged. Ask before adding any dependency
  (e.g. leaflet.markercluster).

When finished: run all tests, build and lint; check "Done when" for Phase 3;
summarise and STOP. Wait for my approval before Phase 4.
```

---

## Phase 4: Booking flow and payments

**Goal:** the core product. A user picks a slot on a BookMyShow-style grid, the slot is held for 5 minutes while they pay ₹199 (Razorpay test mode), and they receive an OTP. They can see and cancel bookings, and use "Charge now" at a free charger.

**Owner:** A (API), C (web app). **Effort:** 7–8 person-days.

### Before starting (you do these)
- [ ] Create a free **Razorpay** account and switch to **Test mode**. Copy the test **Key ID** and **Key Secret** into `backend/.env`, and the Key ID into `frontend/user-web/.env`.
- [ ] Create a **webhook secret** in Razorpay (Settings → Webhooks). The webhook URL itself is set in Phase 7 once the API is deployed; locally we rely on the signature check.

### Tasks

**4.1 State machine: `app/features/bookings/state_machine.py`**
- [ ] One table of allowed transitions, **identical** to the database trigger's table (`architecture.md` 6.1).
- [ ] `transition(booking, new_status, actor, reason)` is the **only** way code changes a booking's status. Illegal changes raise a clear error.
- [ ] Tests: every allowed transition works; every other one is rejected, in Python **and** by the database.

**4.2 OTP: `app/features/bookings/otp.py`**
- [ ] Generates a 6-digit code that is unique among live bookings at the same station within its valid window.
- [ ] Stores **HMAC-SHA256** (server secret `OTP_SECRET` in `.env`), never the code itself.
- [ ] Validity check: start − 15 min to start + 10 min, not used yet.
- [ ] Tests: correct code, wrong code, too early, too late, already used, uniqueness collision.

**4.3 Create a booking: `POST /bookings`**
- [ ] Input: charger, start time, number of blocks (1–4), optional vehicle.
- [ ] Checks: blocks aligned to 30 minutes; start in the future and within 7 days; the charger is in service; **the user has no unpaid energy bill**.
- [ ] Expires stale holds on that charger in the same transaction (lazy check), then inserts the booking as `HELD` with `hold_expires_at = now + 5 min`.
- [ ] Database says the slot is taken (`23P01`) → **409 `SLOT_TAKEN`** with alternatives: nearby times on the same charger, other compatible chargers at the same station, and the top 3 nearby stations from the recommendation engine.
- [ ] User already has a hold → **409 `ACTIVE_HOLD_EXISTS`** with a link to that hold.

**4.4 Payments: `app/features/payments/`**
- [ ] Creates a Razorpay **order for ₹199** (in paise), `receipt = booking_id`, `purpose = BOOKING_FEE`.
- [ ] `POST /payments/verify`: verifies Razorpay's signature → payment `CAPTURED` → booking `CONFIRMED` → generates the OTP → returns it **once**.
- [ ] `POST /payments/webhook`: verifies the webhook signature, processes each event **once** (`webhook_events`), and confirms the booking if `/verify` was missed (e.g. the browser closed).
- [ ] **Late payment** (arrives after the hold expired): try to re-book the same slot. If it's gone, record a full refund and tell the user.
- [ ] Razorpay Checkout's `timeout` is set slightly under the 5-minute hold.

**4.5 Booking management**
- [ ] `GET /me/bookings?scope=upcoming|past` and `GET /bookings/{id}` (owner only).
- [ ] `POST /bookings/{id}/otp`: issues a **new** OTP (replacing the old one) for a `CONFIRMED` booking before its window ends.
- [ ] `POST /bookings/{id}/cancel`:
  - `HELD` → `CANCELLED` (nothing was paid).
  - `CONFIRMED` → `CANCELLED` with the refund from `refunds.py`.
- [ ] `refunds.py`: a pure function `refund_for(cancelled_at, start, fee)` implementing the tiers (100% / 75% / 50% / 0%). The refund is recorded on the payment; in test mode it may also call Razorpay's test refund API.
- [ ] Tests at **every tier boundary** (exactly 2 h, 30 min, 15 min before start).

**4.6 Instant booking ("Charge now"): `POST /bookings/instant`**
- [ ] For a free charger: books from now until the earlier of (next booking − 5 min) or (now + 1 h; changed from 2 h at the owner request).
- [ ] No fee. Goes straight to `CONFIRMED` and returns the OTP.
- [ ] The same unpaid-bill check and overlap protection apply.

**4.7 Vehicles: `app/features/vehicles/`**
- [ ] `GET/POST/PATCH/DELETE /me/vehicles`: nickname, connector type, battery kWh, default flag.
- [ ] Used to pre-fill the connector filter, cost estimates and (in Phase 5) the energy cap.

**4.8 Web app: slot picker (BookMyShow style)**
- [ ] On the station page: date tabs (today + 6 days) → a grid with **chargers as rows** and **30-minute blocks as columns**.
- [ ] Colours for free, booked, held, past, out of service and selected. Legend shown.
- [ ] Select **1–4 adjacent blocks** on one charger; the summary panel shows the charger, the IST time range, the ₹199 fee and an estimated energy cost.
- [ ] **"Hold & pay"** → a 5:00 countdown → Razorpay Checkout (script from `checkout.razorpay.com`).
- [ ] **Slot-taken** dialog that lists the alternatives from 4.3.

**4.9 Web app: confirmation and My Bookings**
- [ ] Confirmation page: **large OTP**, station, charger, time, "valid from 15 min before start", Navigate button, and a warning that the code is shown once (with the option to issue a new one).
- [ ] **My Bookings** (`/bookings`): Upcoming and Past tabs, status badges, **cancel with a refund preview** ("You'll get ₹149.25 back"), "Show new OTP".
- [ ] **Charge now** button on free chargers in the station page.
- [ ] **Vehicles** page in the user profile.

**4.10 Tests**
- [ ] **Concurrency test:** two threads with separate DB connections book the same slot at the same moment → **exactly one** succeeds, the other gets `SLOT_TAKEN`.
- [ ] Hold expiry is respected lazily; the one-hold-per-user rule works.
- [ ] Signature verification: valid passes, tampered fails.
- [ ] Webhook processed once even if sent twice.
- [ ] An unpaid bill blocks new bookings (using a seeded `DUE` session).
- [ ] Instant-booking window calculation (with and without a later booking).

**As built (differences from the task list above):**
- Every endpoint is under `/api` like the rest of the API: `POST /api/bookings`, `POST /api/bookings/instant`, `GET /api/bookings/{id}`, `GET /api/me/bookings`, `POST /api/bookings/{id}/otp`, `POST /api/bookings/{id}/cancel`, `/api/payments/...`, `/api/me/vehicles`.
- Extra endpoints the screens need: `POST /api/payments/orders` (creates or re-uses the Razorpay order for a held booking; `POST /bookings` itself only holds the slot), `GET /api/bookings/{id}/cancel-preview` (the refund shown before confirming) and `GET /api/me/dues` (unpaid bills, for the banner and the Payment due tab).
- Errors carry extra facts in `error.details` (the alternatives for `SLOT_TAKEN`, the booking id for `ACTIVE_HOLD_EXISTS`).
- `BookingOut.server_time` lets the browser count the hold down without trusting its own clock.
- The API returns the public Razorpay Key ID with each order, so the web app needs no Razorpay variable.
- Refunds are recorded on the payment and the booking; in test mode no call is made to Razorpay's refund API.
- `OTP_SECRET` and the `RAZORPAY_*` values are optional at startup; the endpoints that need one answer 503 `SETTING_MISSING`.

### Done when
- [ ] You can book a slot, pay with Razorpay's test UPI ID (`success@razorpay`) or a test card, and see the OTP.
- [ ] Two browsers trying the same slot: one succeeds, the other sees alternatives.
- [ ] Abandoning payment frees the slot after 5 minutes.
- [ ] Cancelling shows and records the correct refund for each tier.
- [ ] "Charge now" works on a free charger and gives an OTP without a fee.
- [ ] All tests pass, including the concurrency test.

### Prompt for Claude Code
```text
We are building ChargeSpot. Read docs/architecture.md (sections 5.3, 6, 7.1, 7.2,
8 and 14) and docs/phases.md before doing anything. Follow "Rules for every phase".

Do PHASE 4 only: "Booking flow and payments", tasks 4.1–4.10.
Create branch phase-4-booking.

Inputs: RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET and OTP_SECRET
are in backend/.env; VITE_RAZORPAY_KEY_ID is in frontend/user-web/.env (test mode).

Key constraints:
- All status changes go through state_machine.transition(); its table must match
  the database trigger exactly.
- The database exclusion constraint is the source of truth for overlaps. Catch
  error 23P01 and return 409 SLOT_TAKEN with alternatives.
- Amounts are calculated only on the server. A booking is CONFIRMED only after the
  server verifies Razorpay's signature (or a verified webhook). Webhooks are
  idempotent.
- OTPs: 6 digits, stored only as HMAC-SHA256, unique per station in their window,
  shown to the user once.
- refunds.py is a pure function with tests at every tier boundary.
- Write the concurrency test (two simultaneous bookings, exactly one succeeds).
- Use the approved razorpay Python SDK; load Razorpay Checkout via its script tag.
  Ask before any other dependency.

When finished: run all tests, build and lint; check "Done when" for Phase 4;
summarise (include how to do a test payment) and STOP. Wait for my approval before
Phase 5.
```

---

## Phase 5: Background jobs, charger simulator and realtime

**Goal:** the system runs itself. Holds expire, no-shows are marked, chargers are reserved before bookings, sessions auto-stop, and outside usage is handled. Every screen updates live. App users get a live charging page.

**Owner:** A. **Effort:** 4–5 person-days.

### Tasks

**5.1 Charging sessions and energy simulation: `app/features/charging/`**
- [ ] `energy.py`: pure functions. Live kWh = power × hours × efficiency (0.9), capped by vehicle battery × (100% − start charge %). Start charge defaults to 20% if unknown. Also battery %, time left and bill amount.
- [ ] The same formula must exist in SQL (for jobs). A test checks both give the same result.
- [ ] `GET /me/sessions/{id}` (live values) and `POST /me/sessions/{id}/stop`.

**5.2 Charger simulator: `app/features/chargers/`**
- [ ] Physical charger status (`AVAILABLE`, `RESERVED`, `CHARGING`, `FAULTED`, `OUT_OF_SERVICE`) changes only through simulated OCPP-style events, logged in `charger_events`.
- [ ] Admin endpoint `POST /admin/chargers/{id}/simulate` with events `EXTERNAL_START`, `EXTERNAL_STOP`, `FAULT`, `RECOVER`, `UNPLUG`.
- [ ] `EXTERNAL_START` during a reservation lock is **rejected**, just as a real reserved charger would refuse.
- [ ] Outside sessions are recorded as `charging_sessions` with `source = EXTERNAL`, and availability shows `BUSY_EXTERNAL` for the current block.

**5.3 Job functions: migration `011_jobs.sql`** (planned as `009`; 009 and 010 were already taken)
- [ ] `expire_holds(p_now)`, `apply_reservation_locks(p_now)`, `resolve_occupied_starts(p_now)`, `mark_no_shows(p_now)`, `auto_stop_sessions(p_now)`, exactly as described in `architecture.md` section 10.
- [ ] Every function takes `p_now timestamptz DEFAULT now()` so tests can pretend it's any time.
- [ ] They change bookings only through legal transitions (the trigger enforces this) with actor `SYSTEM`.
- [ ] `resolve_occupied_starts`: move the booking to another free compatible charger at the same station, otherwise cancel with a **100% refund**.
- [ ] `auto_stop_sessions`: stops at slot end, and calculates `bill_amount` with `bill_status = DUE` for app and instant sessions.

**5.4 Schedule: migration `012_cron.sql`** (planned as `010`)
- [ ] `cron.schedule` runs each job **every minute** (only when `pg_cron` exists).

**5.5 Lazy checks in the API**
- [ ] One helper runs the relevant checks for a charger or station before availability, booking and session reads, so results are right even if a job hasn't run yet.

**5.6 Realtime: migration `013_realtime.sql` and the web app** (planned as `011`)
- [ ] Triggers on `bookings`, `chargers` and `charging_sessions` send a small message (`{station_id, charger_id}`) to the topic `station:<id>` using Supabase `realtime.send`. **No booking details in the message.**
- [ ] Web app `lib/realtime.ts`: subscribe to the stations on screen and **re-fetch from the API** when nudged. If realtime fails, fall back to polling every 30 seconds.
- [ ] Availability grids, the map and My Bookings update live.

**5.7 Web app: live charging page `/charging/:sessionId`**
- [ ] Progress ring (battery %), kWh, cost so far, time left, Stop button.
- [ ] **Warning banner 5 minutes before auto-stop**.
- [ ] After stopping: a summary with the bill. The **Pay** button comes in Phase 6.
- [ ] My Bookings links to the live page for `ACTIVE` bookings.

**5.8 Tests** (call job functions directly with chosen `p_now`)
- [ ] A hold expires at exactly 5 minutes, not before.
- [ ] Reservation lock at start − 15 min; external start rejected during the lock.
- [ ] No-show at start + 10 min, fee kept; slot is then free.
- [ ] Occupied at start → moved to another charger; no charger free → cancelled with a 100% refund.
- [ ] Auto-stop at slot end with the correct bill.
- [ ] Python and SQL energy formulas match.

**As built (differences from the task list above):**
- The migrations are `011_jobs.sql`, `012_cron.sql` and `013_realtime.sql` (009 and 010 were already used by row-level security and search). `012` enables `pg_cron` and does nothing on a database without it.
- One cron entry, `chargespot-jobs`, runs `run_due_jobs()` every minute. It calls the five job functions in the order that gives the right answer (expire holds, resolve occupied starts, no-shows, auto-stop, reservation locks). Each job still takes `p_now` and an optional station, and can be called alone.
- The lazy checks (`features/jobs/lazy.py`) run `run_due_jobs` for the station involved before availability, booking and session reads. If they fail, the read carries on.
- The energy formula multiplies first and divides last in both Python and SQL; a 20,000-case random comparison found no difference. Shared numbers sit in the `job_rules` table, and a test checks it equals `config.py`.
- Booking notices (moved / warned / cancelled for lack of a charger) are stored on the booking (`notice_kind`, `notice_text`, `moved_from_charger_id`).
- The availability grid has a `BUSY_EXTERNAL` block state for the current block while an outside session runs.
- Extra endpoints: `GET /api/me/sessions/active` (the Charging tab and app-bar pill), `POST /api/admin/bookings/{id}/start` (stands in for the kiosk until Phase 6). `python -m scripts.simulate` runs the simulator and the jobs from the command line without a login token; `python -m scripts.make_admin` makes an account an admin.
- Walk-in sessions (Phase 6) are already handled by `auto_stop_sessions`: they stop 5 minutes before the next booking or when the prepaid amount is used up.
- A realtime nudge goes to `station:<id>` with only `{station_id, charger_id}`. The web app reads nothing else from it.

### Done when
- [ ] Without touching anything: an unpaid hold disappears after 5 min, a booking with no OTP becomes `NO_SHOW` at +10 min, and a session stops at slot end.
- [ ] "Simulate external session" on a booked charger triggers the move-or-refund behaviour.
- [ ] Two browsers on the same station page: booking in one updates the other within a couple of seconds.
- [ ] The live charging page updates, warns at 5 minutes, and auto-stops.
- [ ] All tests pass.

### Prompt for Claude Code
```text
We are building ChargeSpot. Read docs/architecture.md (sections 6, 7.4, 10 and 11)
and docs/phases.md before doing anything. Follow "Rules for every phase".

Do PHASE 5 only: "Background jobs, charger simulator and realtime", tasks 5.1–5.8.
Create branch phase-5-jobs-realtime.

Key constraints:
- Jobs are SQL functions scheduled with pg_cron (every minute). Each takes
  p_now timestamptz DEFAULT now() for testability, and changes bookings only via
  legal transitions with actor SYSTEM.
- Keep the lazy checks in the API so correctness never depends on job timing.
- The energy formula must be identical in Python and SQL; test that they agree.
- Realtime messages carry only {station_id, charger_id}; clients re-fetch from the
  API. Fall back to 30-second polling if realtime fails.
- The charger simulator must reject EXTERNAL_START during a reservation lock.
- Ask before adding any dependency.

When finished: run all tests, build and lint; check "Done when" for Phase 5;
summarise (include how to demo each job) and STOP. Wait for my approval before
Phase 6.
```

---

## Phase 6: Station kiosk and energy billing

**Goal:** the station kiosk app (status board, OTP start, walk-in QR payment) and energy bill payment in the web app. After this phase, the whole user journey works end to end.

**Owner:** D (kiosk), A (API), C (bill payment UI). **Effort:** 6–7 person-days.

### Tasks

**6.1 Kiosk app scaffold: `frontend/kiosk/`**
- [ ] React + Vite + TypeScript + Tailwind, part of the npm workspace, using `@chargespot/shared`.
- [ ] Designed for a **landscape tablet**: large touch targets, readable from 1 m, fullscreen, dark theme matching the web app.
- [ ] `qrcode.react` for QR codes (approved).

**6.2 Kiosk device login**
- [ ] Admin endpoint `POST /admin/stations/{id}/devices` creates a kiosk key `ks_<prefix>_<secret>`, returned **once**. Only the SHA-256 hash is stored.
- [ ] Kiosk **setup screen**: paste the key once; it's stored on the tablet.
- [ ] API dependency `get_current_device` reads the `X-Device-Key` header, updates `last_seen_at`, and **limits the device to its own station**.

**6.3 Kiosk API: `app/features/kiosk/`**
- [ ] `GET /kiosk/status`: station name, and for each charger its state, progress %, "free until", price, and a walk-in summary ("₹120 of ₹200 used"). **No names, phone numbers or bills.**
- [ ] `POST /kiosk/otp-start {otp}`: finds the matching booking at this station within its window → `ACTIVE` → creates the session → starts the simulated charger → returns which charger to use.
- [ ] Wrong-OTP rule: after 5 wrong tries, a **2-minute cooldown** for the device; **20+ wrong tries in 10 minutes** creates an admin alert.
- [ ] `POST /kiosk/walk-ins {charger_id, amount | until_next}` → creates a `WALK_IN` booking (`HELD`, 3-minute hold) up to (next booking − 5 min) → creates a **Razorpay Payment Link** for the amount → returns its URL for the QR.
- [ ] `GET /kiosk/walk-ins/{id}`: payment status, for the kiosk to show progress (plus realtime nudges).
- [ ] Webhook `payment_link.paid` → booking `HELD → ACTIVE` → session with `prepaid_amount` → charger starts.

**6.4 Walk-in settlement**
- [ ] `auto_stop_sessions` also stops when the prepaid amount is used up.
- [ ] On stop: `bill_status = PREPAID_SETTLED`; the unused amount is recorded as a refund on the payment.
- [ ] Walk-in stops from the charger simulator (`UNPLUG`) also settle correctly.

**6.5 Kiosk screens**
- [ ] **Status board:** a tile per charger with state, progress bar, "free until" and price; station name and IST clock; buttons **"Start with OTP"** and **"Take a charger"**.
- [ ] **OTP pad:** a big numeric keypad; shows the cooldown time; success screen "Go to Charger ③, plug in".
- [ ] **Walk-in:** pick a free charger → choose ₹100 / ₹200 / ₹500 / "until next booking" (with the kWh estimate) → QR with a 3-minute countdown → "Payment received ✓, plug in at Charger ③" → the tile then shows "Done · used ₹186 · ₹14 refunded" for 2 minutes.
- [ ] **Auto-reset** to the status board after 30 seconds without a touch.
- [ ] **Connection lost** banner, and retry, if the API can't be reached.

**6.6 Energy bill payment in the web app**
- [ ] `POST /me/sessions/{id}/pay` → Razorpay order for `bill_amount` (`purpose = ENERGY`) → verify → `bill_status = PAID`.
- [ ] Live charging page summary gets a **Pay ₹X** button.
- [ ] My Bookings: **"Pending payment"** section.
- [ ] A banner on booking pages when the user has dues: *"Clear ₹223.20 to book again"*.
- [ ] Receipt view for paid sessions (kWh, rate, amount, payment ID, IST times).

**6.7 Tests**
- [ ] OTP start: success, wrong code, outside window, reused code, cooldown after 5 wrong tries, alert after 20.
- [ ] A device **cannot** start or see another station's chargers.
- [ ] A walk-in **cannot** overlap an upcoming booking; an unpaid walk-in expires after 3 min and frees the charger.
- [ ] Payment-link webhook processed once; leftover refund calculated correctly.
- [ ] Energy bill payment marks `PAID`; dues block new bookings until paid.

**As built (differences from the task list above):**
- Migration `014_kiosk.sql`: the `admin_alerts` table (the kiosk raises `KIOSK_OTP_GUESSING` into it; the admin page that shows alerts is Phase 7) and new versions of `finish_session` and `auto_stop_sessions`. Migration 011 was not edited.
- Routes live under `/api` like the rest of the API: `GET /api/kiosk/status`, `POST /api/kiosk/otp-start`, `POST /api/kiosk/walk-ins`, `GET /api/kiosk/walk-ins/{id}`, `POST /api/kiosk/walk-ins/{id}/cancel` (the "Cancel" button on the QR screen frees the charger at once), `POST /api/admin/stations/{id}/devices`, `GET /api/admin/stations/{id}/devices`, `POST /api/admin/devices/{id}/disable`, and for drivers `POST /api/me/sessions/{id}/pay`, `POST /api/me/sessions/{id}/pay/verify`, `GET /api/me/sessions/{id}/receipt`.
- Kiosk keys are `ks_<8 hex>_<secret>`; only the prefix and a SHA-256 hash are stored. Until the admin pages exist, `python -m scripts.make_kiosk_key "<station name>"` makes a key (it prints it once).
- Wrong codes: a "streak" counts wrong tries since the last right one. Every 5th wrong try starts a 2-minute wait (`429 OTP_COOLDOWN` with `retry_after_seconds`), and the wait comes again after 5 more. The right code typed too early or too late answers `OTP_NOT_VALID_NOW` and counts as a wrong try. A right code on a charger that cannot start (broken, or an outside driver is on it) answers `CHARGER_UNAVAILABLE` and does not count as a guess. 20 wrong tries in 10 minutes make one alert per 10 minutes.
- A walk-in's time window is the same rule as "Charge now": from now to the earlier of 1 hour (first 2 hours, changed later) and 5 minutes before the next booking, and only if at least 15 minutes fit. "Until the next booking" is priced by the server for the whole window (the energy a vehicle with the default 40 kWh battery can take, rounded up to a whole rupee). A charger without a known price or power cannot take walk-ins (`PRICE_UNKNOWN`).
- Razorpay payment links must live at least 15 minutes, so the link is not given a short expiry: our own 3-minute hold decides. A payment that arrives after the hold ran out, after "Cancel", or when the charger broke meanwhile is refunded in full (recorded).
- A walk-in is marked paid only when Razorpay itself says so: through the `payment_link.paid` webhook, or (while no webhook is registered, as in development) because the kiosk's own poll asked Razorpay about the link (`payment_link.fetch`, at most once every 3 seconds per link). Both paths end in the same function, which runs once.
- Settlement happens inside `finish_session` (so unplugging, the job and the admin button all settle the same way): a walk-in is billed at most what it prepaid (the energy is cut back to what the money buys, because the job runs once a minute), the leftover is recorded as `refunded_amount` on the payment (and `refund_amount` on the booking), and `bill_status` is `PREPAID_SETTLED`. A walk-in session now also stops when its booked window ends.
- The kiosk asks for the status board every 4 seconds and for a walk-in every 2 seconds. It does not use Supabase Realtime: that would put the Supabase key on a shared tablet.
- The energy bill: `ENERGY` payments follow the booking-fee steps (order, Checkout, signature check, webhook as backup). The receipt page is `/receipts/session/:sessionId`, because `/receipts/:bookingId` already shows the booking-fee receipt. "Print / save as PDF" uses the browser's print dialog and a print stylesheet in `index.css`.
- `frontend/shared/src` now imports its own files with the `.ts` ending, so Node's test runner can load `@chargespot/shared` (needed by the kiosk's unit tests).
- Not done here: the admin alerts page, a Realtime connection for the kiosk, and a run on a real tablet.

### Done when
- [ ] **Full app journey:** book → pay ₹199 → OTP → enter at kiosk → charging progress on phone and kiosk → auto-stop → pay energy bill in the web app.
- [ ] **Full walk-in journey:** kiosk → pick charger → choose amount → scan QR with a phone → pay (test mode) → charging → leftover refund shown.
- [ ] The kiosk resets itself, shows no personal data, and handles the API being offline.
- [ ] All tests pass.

### Prompt for Claude Code
```text
We are building ChargeSpot. Read docs/architecture.md (sections 7, 8, 9 and 14)
and docs/phases.md before doing anything. Follow "Rules for every phase".

Do PHASE 6 only: "Station kiosk and energy billing", tasks 6.1–6.7.
Create branch phase-6-kiosk.

Key constraints:
- The kiosk is shared by everyone: show no names, phone numbers or bills; reset
  after 30 s idle; it only starts charging (OTP or walk-in). App users stop and pay
  in the web app.
- Kiosk auth is a per-station device key (hashed in the DB) in the X-Device-Key
  header; a device can only act on its own station.
- Wrong OTPs: 5 tries then a 2-minute device cooldown; 20+ in 10 minutes creates
  an admin alert.
- Walk-ins: WALK_IN booking HELD for 3 minutes while the QR (Razorpay Payment Link)
  is shown; charging starts only after the verified webhook; prepaid leftovers are
  recorded as refunds. Walk-ins are protected by the same no-overlap constraint.
- Use the approved qrcode.react. Ask before any other dependency.

When finished: run all tests, build and lint; walk through both "Done when"
journeys and report the result; summarise and STOP. Wait for my approval before
Phase 7.
```

---

## Phase 7: Admin, hardening, docs and deployment

**Goal:** admin tools, every edge case handled, a full test suite with CI, complete docs, everything deployed on free hosting, and a rehearsed demo for the jury.

**Owner:** everyone (D leads docs and deployment). **Effort:** 6–8 person-days.

### Tasks

**7.1 Admin area in the web app (`/admin`, role `ADMIN`)**
- [ ] **Stations:** search, create and edit (manual), mark inactive; the data source badge is visible.
- [ ] **Chargers:** create and edit (connector, power, price), set **out of service**. If it has future bookings, show them and offer to **cancel them with a full refund**.
- [ ] **Kiosk devices:** create a key (shown once), revoke, last seen.
- [ ] **Charger simulator panel:** buttons for each simulated event, including "Simulate external session".
- [ ] **Alerts:** kiosk OTP-guessing alerts, failed webhooks.
- [ ] **Reports:** bookings by status, no-shows, revenue (booking fees, energy, walk-ins), refunds, and **operator settlement** (energy revenue per operator).
- [ ] `backend/scripts/make_admin.py <email>` to promote a user.

**7.2 Edge cases (each one handled and tested)**
- [ ] Charger goes out of service with future bookings.
- [ ] Payment arrives after the hold expired (re-book or refund).
- [ ] Booking across midnight IST.
- [ ] Double-clicking "Pay"; refreshing during payment; closing the tab after paying (the webhook confirms).
- [ ] Login token expires mid-flow (redirect to login, then return).
- [ ] Razorpay, OSRM, Nominatim or Realtime unavailable: clear messages and fallbacks.
- [ ] The kiosk's clock is wrong: all times come from the server.
- [ ] A vehicle is deleted while it has bookings.

**7.3 Tests and CI**
- [ ] Fill test gaps; aim for complete coverage of `bookings`, `payments`, `kiosk`, `charging`, `recommendations` and the job functions.
- [ ] **GitHub Actions** (free): starts a PostgreSQL service with `btree_gist`, runs the migrations, runs `pytest`, then `npm ci`, `build` and `lint` for both apps.
- [ ] Optional: front-end unit tests for slot-grid selection and formatting with `vitest` (ask first).

**7.4 Documentation**
- [ ] `docs/booking-flow.md`: every flow as a diagram (booking, payment, OTP start, walk-in, no-show, occupied charger, refunds).
- [ ] `docs/api.md`: key endpoints and examples, plus a pointer to the live `/docs`.
- [ ] `docs/setup.md`: complete local setup from a fresh clone.
- [ ] `docs/demo-script.md`: the jury demo (see 7.6).
- [ ] **README.md:** what ChargeSpot is, screenshots, features, architecture diagram, how to run, test accounts (test mode), **team members and roles**, data attribution and licences.

**7.5 Deployment (free tiers)**
- [ ] **Database:** run the migrations and seed on the Supabase project; check pg_cron jobs are scheduled and Realtime is enabled.
- [ ] **API → Render** (free web service): root `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, all env vars set.
- [ ] **Web app and kiosk → Vercel**: two projects with root directories `frontend/user-web` and `frontend/kiosk`, env vars set.
- [ ] **Google OAuth:** add the production URLs to the authorised origins and redirect URIs.
- [ ] **Razorpay:** set the webhook URL to the Render API; test mode stays on.
- [ ] `CORS_ORIGINS` and `FRONTEND_URL` set to the production URLs.
- [ ] **Smoke test** in production: login, search, book, pay, OTP at the kiosk, walk-in QR, energy bill.

**7.6 Jury demo script (about 10 minutes)**
1. **Problem and idea** (1 min): EV drivers can't reserve chargers; ChargeSpot is "BookMyShow for charging".
2. **Discover** (1 min): map of Ahmedabad, address search, "approximate data" badge, best-station suggestions with reasons.
3. **Book** (2 min): slot grid → hold with countdown → Razorpay test payment → OTP.
4. **Charge** (2 min): enter OTP at the kiosk → live progress on phone and kiosk → 5-minute warning → auto-stop → pay the energy bill.
5. **Walk-in** (1 min): kiosk → pick a charger → scan QR → pay → charging → leftover refund.
6. **Reliability** (2 min): two browsers book the same slot (only one wins, shown with the database constraint); simulate an external session on a booked charger (auto-move); show `booking_events` as the audit trail.
7. **Engineering** (1 min): architecture diagram, tests and CI, free stack.
- [ ] Rehearse it on the deployed version. Open the apps a minute early (Render cold start).

**7.7 Final clean-up**
- [ ] Remove dead code and leftover TODOs; lint clean; consistent comments.
- [ ] Every `.env.example` is complete; no secrets in git history going forward.

**As built so far (group a: 7.1 and 7.2; the rest of Phase 7 is not done):**
- Migration `015_admin.sql`: charger events `OUT_OF_SERVICE` and `RESTORE` (a repair `RECOVER` still only mends a faulted charger), the alert kind `WEBHOOK_FAILED`, and indexes for the admin lists. `apply_charger_event` was replaced; 011 stays as applied.
- API: `features/admin/` (`/api/admin/overview`, `reports`, `operators`, `stations` list/detail/edit, chargers add/edit, `chargers/{id}/affected`, `out-of-service`, `restore`, `events`, `bookings` and `bookings/{id}/events`, `devices`, `alerts` and `alerts/{id}/seen`). Every route needs the role ADMIN on the server (a test calls each one as a driver and without a token). Creating a station is the existing `POST /api/stations`; kiosk keys are the Phase 6 endpoints.
- **Out of service never breaks a booking silently.** With future bookings the server answers `409 HAS_FUTURE_BOOKINGS` and changes nothing; the admin page lists them first (time, driver, status, fee paid). Confirming cancels each with a full refund of what was paid (recorded, as everywhere in test mode), a `CANCELLED_NO_CHARGER` notice for the driver and a `booking_events` row by `ADMIN`. A session in progress is stopped and billed up to that moment. The same rule guards taking a whole station off the map (`PATCH` with `is_active = false`, `cancel_bookings = true` to confirm).
- Entering a power or price for a charger counts as real data: the charger becomes `manual` and loses its "Approximate" tag.
- Failed webhooks: a call with a bad signature, or an event that fails while being processed, raises a `WEBHOOK_FAILED` alert (the same alert at most once per 10 minutes); a failing event is undone and answered with an error so Razorpay retries it.
- Reports use India-time days. Revenue is net of refunds; "operator settlement" is energy revenue (paid energy bills plus walk-in sessions) per station operator.
- Web: `/admin` (Overview with tiles, two plain-SVG charts and the reports; Stations with search, sort, pages and an edit form; chargers with add/edit and the out-of-service dialog; Bookings with filters and a history timeline; Kiosks with create-key-shown-once and revoke; Simulator with a live event log; Alerts with mark as seen). No chart library was added. New shared components: `DataTable`, `Pagination`, `StatTile`, `ColumnChart`, `BarList`, `ConfirmDialog`.
- Edge cases (7.2): out of service with bookings (above); late payment after the hold (existing: re-book or refund, tested); a booking across midnight India time (appears on both days, tested); double-click Pay (the button ignores a second tap while one is open; the server returns the same order); closing the tab after paying (the webhook confirms); a deleted vehicle keeps its bookings (the link becomes empty, charging uses the default battery, tested); an expired login redirects to Sign in with a notice and returns to the page; Razorpay, OSRM, Nominatim and Realtime failures keep their clear messages and fallbacks (tests already existed); the kiosk takes all times from the server.
- Polish: an error page, a 404 page, an offline notice, a session-ended notice, one `h1` per page, unique ids, tap areas of 44 px. The audit and its findings are in `docs/audit.md`.
- **The admin got its own screen and the management pages (added after group a, at the owner's request):** `/admin` is no longer inside the driver layout: it has its own header ("Back to the app", sign out) and a grouped sidebar (Overview; Network: Stations, Operators, Kiosks, Simulator; Business: Bookings, Payments; People: Users and roles; System: Alerts, Activity log), tabs on a phone.
- **Users and roles:** list and search accounts, make someone an admin or an ordinary driver. An admin cannot change their own role (`CANNOT_CHANGE_OWN_ROLE`) and the last admin can never be removed (`LAST_ADMIN`). The role is read from the database on every request, so a change works at once (the person reloads the app to see the Admin link).
- **Operators:** add, rename, delete (only with no stations: `OPERATOR_IN_USE`); a station's operator is set on its edit page.
- **Kiosk keys:** create, rename, replace (rotate: a new key for the same tablet and station, the old key dies at once) and revoke, all from the Kiosks page; a key is shown once.
- **Payments:** every booking fee, energy bill and walk-in payment with its refunds, filters and totals.
- **Activity log** (`admin_actions`, migration 016): who changed what (roles, kiosk keys, out of service, station, charger and operator edits), shown on its own page.

### Done when
- [ ] An admin can manage stations, chargers, devices and the simulator, and see reports.
- [ ] Every edge case in 7.2 is handled and tested.
- [ ] CI is green on `main`.
- [ ] Everything is live on Supabase, Render and Vercel, and the smoke test passes.
- [ ] README and docs are complete; the demo has been rehearsed end to end.

### Prompt for Claude Code
```text
We are building ChargeSpot. Read docs/architecture.md and docs/phases.md fully
before doing anything. Follow "Rules for every phase".

Do PHASE 7 only: "Admin, hardening, docs and deployment", tasks 7.1–7.7.
Create branch phase-7-release.

Work in this order and pause for my confirmation between groups:
  (a) 7.1 admin area and 7.2 edge cases,
  (b) 7.3 tests and CI,
  (c) 7.4 documentation and 7.6 demo script,
  (d) 7.5 deployment — give me a step-by-step checklist for the parts I must do in
      the Supabase, Render, Vercel, Google Cloud and Razorpay dashboards, and do
      the code/config parts yourself,
  (e) 7.7 final clean-up.

Key constraints:
- Admin routes require role ADMIN on the server, not just a hidden UI.
- Taking a charger out of service must never silently break future bookings.
- CI uses only free GitHub Actions and a PostgreSQL service container.
- README must include team roles and OSM/OCM attribution.
- Ask before adding any dependency (e.g. vitest).

When finished: run everything; report the CI status, deployed URLs and smoke-test
results; summarise and STOP.
```
