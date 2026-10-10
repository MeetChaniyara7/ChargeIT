# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ChargeSpot is "BookMyShow for EV charging", a college final-year project built only with free tools. Read `docs/architecture.md` (what and why) and `docs/phases.md` (build plan, one phase at a time, each needing the user's approval) before starting work.

Repository layout:

- `backend/`: FastAPI + SQLAlchemy 2.x + psycopg 3 (Python 3.12). Package `app/`, run as `uvicorn app.main:app`.
- `frontend/user-web/`: React 19, Vite, TypeScript, Tailwind v4, Leaflet.
- `frontend/shared/`: `@chargespot/shared` (constants mirroring the DB CHECK lists, `formatINR`/`formatIST`, generated API types). Consumed as TypeScript source, no build step.
- `frontend/kiosk/` arrives in Phase 6.
- `database/`: `migrate.py`, `migrations/` (numbered SQL), `seeds/`, `imports/` (OSM/OCM import and cleaning), `queries/` (saved read-only SQL). Filled from Phase 2.
- Full tree: `docs/architecture.md` section 4.

## Commands

API (from `backend`, with `.venv` active: `.venv\Scripts\activate` on Windows):

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000   # docs at http://localhost:8000/docs
python -m pytest                            # tests need no database
python -m pytest tests/test_auth.py::test_token_round_trip   # single test
```

JavaScript (from the repo root; npm workspaces):

```bash
npm install
npm run dev:web              # http://localhost:5173
npm run build                # tsc -b && vite build for every workspace (this is the type check)
npm run lint                 # oxlint (config in frontend/user-web/.oxlintrc.json)
npm run generate:api-types   # API must be running; regenerates frontend/shared/src/api-types.ts
```

Database (from the repo root, backend venv active; URLs come from `backend/.env`):

```bash
python -m database.pipeline              # migrate + import + dedupe + synthetic + demo data (re-runnable)
python -m database.migrate --status      # which migrations ran
python -m pytest database/tests          # needs TEST_DATABASE_URL (a throwaway LOCAL db; tests wipe it)
```

## Architecture

**Config:** every setting comes from env vars via `app/config.py` (`get_settings()`); there are no hard-coded secrets or fallbacks. The API refuses to start without `DATABASE_URL`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID` and `FRONTEND_URL`. Business rules (slot length, fees, windows, refund tiers) live in `BOOKING_RULES` in the same file.

**API layout:** `app/main.py` only builds the app. Each feature in `app/features/<name>/` has `router.py` (HTTP), `service.py` (rules), `repository.py` (queries), `schemas.py` (Pydantic), `models.py` (SQLAlchemy). Cross-cutting code is in `app/core/`.

**Errors:** all errors use one format, `{"error": {"code": "...", "message": "..."}}` (`app/core/errors.py`). Raise `AppError(status, code, message)` for specific codes; plain `HTTPException`s are mapped to a code by status.

**Auth:** the API issues its own JWT (`features/auth/tokens.py`). Use `Depends(get_current_user)` or `Depends(require_admin)` from `features/auth/dependencies.py`. Google sign-in works via the ID-token flow (`POST /api/auth/google`, used by the Google button) and a redirect flow (`/auth/google/login`, protected by a random `state` cookie). Front-end auth routes live under `/auth/*`, with the Google ones also under `/api/auth/*`.

**Database:** PostgreSQL on Supabase. The schema is defined ONLY by numbered SQL files in `database/migrations/`; SQLAlchemy models mirror it and never create tables. Never edit an applied migration; add a new numbered file (and enable row-level security on any new table; a test checks this). Key rules live in the database itself: the `bookings_no_double_booking` exclusion constraint (catch SQLSTATE 23P01; on 40P01 deadlock retry once) and the `allowed_booking_transitions` table plus trigger (pass who/why via `set_config('chargespot.actor'/'chargespot.reason', ..., true)`). One charger row = one bookable plug. `data_source`/`estimated_fields` mark generated values; the app shows only `vehicle_category = 'FOUR_WHEELER'` stations.

**Web app:** feature folders under `src/features/` (`auth`, `stations`, `home`), routes in `src/app/App.tsx`. Every API call goes through `src/lib/api.ts` (`apiFetch`), which adds the Bearer token, parses the error format into `ApiError`, and on 401 clears the token and fires `chargespot:unauthorized` (`AuthContext` listens and signs out). The token is in `localStorage['token']`.

## Rules

- Do only the current phase from `docs/phases.md`, then stop for review.
- Ask before adding any dependency or paid service.
- Never commit `.env` files or anything in `data/legacy/` / `data/raw/`.
- Times are stored in UTC and shown in Asia/Kolkata. Money is shown in ₹ via `formatINR`.

## Environment

- `backend/.env`: see `backend/.env.example` (every variable documented).
- `frontend/user-web/.env`: `VITE_API_URL`, `VITE_GOOGLE_CLIENT_ID` (must equal the API's `GOOGLE_CLIENT_ID`), `VITE_SUPABASE_*` (Phase 5 realtime).
