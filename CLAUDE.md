# CLAUDE.md

> **Before making structural changes, read `docs/FLOW.md` and `docs/architecture.md`.** (`docs/architecture.md` is the design and the reasons; its section 18 is what is built today; `docs/phases.md` is the plan, one phase at a time.) Do not create `docs/ARCHITECTURE.md`: on Windows it is the same file as `docs/architecture.md`.

## Project

ChargeSpot is "BookMyShow for EV charging", a college final-year project built only with free tools. Drivers find stations in Gujarat, hold a 30-minute slot, pay a ₹199 booking fee (Razorpay test mode), get a one-time code, and watch charging live. Status: phases 0 to 4 are on `main`; phase 5 (jobs, simulator, realtime, live charging) is built on branch `phase-5-jobs-realtime`; the kiosk, energy-bill payment, admin area and deployment (phases 6 and 7) are not started. Details: `docs/SPEC.md`, `docs/PLAN.md`.

## Tech stack

- **API:** Python 3.12, FastAPI, SQLAlchemy 2, psycopg 3, Pydantic, PyJWT, bcrypt, httpx, razorpay SDK.
- **Web app:** React 19, Vite 8, TypeScript, Tailwind CSS v4, React Router 7, Leaflet, `@supabase/supabase-js` (Realtime only).
- **Database:** PostgreSQL on Supabase (`btree_gist`, `pg_trgm`, `pg_cron`); numbered SQL migrations.
- **Outside services (free):** Google Sign-In, Razorpay (test mode), OSRM, Nominatim, OpenStreetMap tiles, Supabase Realtime.
- **Tooling:** npm workspaces, oxlint, pytest, Node's built-in test runner (no vitest).

## Folder structure

```
backend/app/            FastAPI app: main.py, config.py, db.py, core/, features/<name>/
backend/scripts/        demo tools: simulate.py, make_admin.py
backend/tests/          pytest (needs_db tests use TEST_DATABASE_URL)
frontend/user-web/      driver web app: src/app, src/components/{layout,ui}, src/features/<name>, src/lib, tests/
frontend/shared/        @chargespot/shared: constants, formatters, parseSearch, estimateEnergy, tokens.css, api-types.ts (generated)
frontend/kiosk/         NOT BUILT (phase 6)
database/               migrations/ (schema), seeds/, imports/, queries/ (saved SQL), tests/, migrate.py, pipeline.py
docs/                   architecture.md (design + section 18: what is built today), FLOW.md, SCHEMA.md, API.md, SPEC.md, PLAN.md, DECISIONS.md, CHANGELOG.md, phases.md, setup.md, data.md, ui-flow.md, ui-prompts.md
data/                   raw downloads and old exports (git-ignored)
```

Each API feature folder has `router.py` (HTTP), `service.py` (rules), `repository.py` (queries, where used), `schemas.py`, `models.py`. The web app keeps pages, components and hooks of one feature together in `src/features/<name>/`.

## Commands

Setup (first time):

```bash
npm install                                   # from the repo root: web app + shared package
cd backend && python -m venv .venv            # then activate: .venv\Scripts\activate (Windows)
pip install -r requirements-dev.txt
# copy backend/.env.example to backend/.env and frontend/user-web/.env.example to frontend/user-web/.env, fill them in
```

Run (two terminals):

```bash
uvicorn app.main:app --reload --port 8000     # in backend, venv active; docs at http://localhost:8000/docs
npm run dev:web                               # in the repo root; http://localhost:5173
```

Build, lint, test:

```bash
npm run build            # tsc -b && vite build for every workspace (this is the type check)
npm run lint             # oxlint
npm run test:web         # web + shared unit tests (node --test)
python -m pytest         # in backend: API tests (needs_db tests are skipped without TEST_DATABASE_URL)
python -m pytest tests/test_auth.py::test_token_round_trip     # one test
python -m pytest database/tests                                # repo root, venv active; needs TEST_DATABASE_URL (a throwaway LOCAL db; tests wipe it)
npm run generate:api-types                    # API must be running; rewrites frontend/shared/src/api-types.ts
```

Database (repo root, backend venv active; URLs come from `backend/.env`):

```bash
python -m database.migrate --status           # which migrations ran
python -m database.migrate                    # apply new migrations
python -m database.pipeline                   # migrate + import + dedupe + synthetic + demo data (re-runnable)
```

Demo tools (in `backend`, venv active; they use `DATABASE_URL`, which is the live Supabase database):

```bash
python -m scripts.simulate list "riya"                          # find chargers by station name
python -m scripts.simulate bookings you@example.com             # a driver's upcoming bookings and ids
python -m scripts.simulate event EXTERNAL_START "Riya Autolink Sola" CCS2-1   # outside driver starts it (refused while reserved)
python -m scripts.simulate event EXTERNAL_STOP "Riya Autolink Sola" CCS2-1
python -m scripts.simulate event UNPLUG "Riya Autolink Sola" CCS2-1           # ends the session and bills it
python -m scripts.simulate event FAULT "Riya Autolink Sola" CCS2-1            # also RECOVER
python -m scripts.simulate start <booking-id>                   # start charging, like the kiosk will
python -m scripts.simulate jobs                                 # run all background jobs once, now
python -m scripts.make_admin you@example.com                    # make an account admin (--remove to undo)
```

## Conventions seen in the code

- **API:** routers hold no rules. Services raise `AppError(status, "CODE", message, details?)`; every error is `{"error": {"code", "message", "details"?}}`. Endpoints are plain `def` with `Depends(get_db)` and `Depends(get_current_user)` / `require_admin`. Services take `now` as an argument so tests control time.
- **Pure modules** (`scoring.py`, `refunds.py`, `energy.py`, `slots.py`, `selection.ts`, `parseSearch`) have no database or network access and their own unit tests.
- **Rules that must always hold live in the database:** `bookings_no_double_booking` (catch SQLSTATE `23P01`; retry once on `40P01`), `allowed_booking_transitions` + trigger (tell it who and why with `state_machine.set_actor()`), and the SQL job functions in `011_jobs.sql`. Lazy checks (`features/jobs/lazy.py`) re-run them before reads.
- **Tests:** pytest with a rolled-back transaction per test (`db` / `db_client` fixtures, `tests/factories.py`); the SQL job tests call functions with a chosen `p_now`.
- **Web app:** function components (`React.FC`), data through `useApiQuery(key, fetcher)` and `apiFetch` (`src/lib`), filters in the URL, hooks in their own files (fast-refresh lint), accessibility built in (labels, roles, 44 px targets, reduced-motion respected).
- **Comments** explain why, in plain language; each module starts with a short docstring.

## Rules

- Do only the current phase from `docs/phases.md`, then stop for review. Each phase needs the owner's approval.
- Ask before adding any dependency, extension or paid service.
- Never commit `.env` files or anything in `data/legacy/` or `data/raw/`.
- Never edit an applied migration: add a new numbered file in `database/migrations/` and enable row-level security on any new table (a test checks this).
- All booking status changes go through `features/bookings/state_machine.py` (`transition()`); a charger's status changes only through `apply_charger_event` / `simulate_charger_event`.
- Do not edit `frontend/shared/src/api-types.ts` by hand: regenerate it with `npm run generate:api-types`.
- Times are stored in UTC and shown in Asia/Kolkata. Money is shown in ₹ with `formatINR` (or `components/ui/Money.tsx`). Amounts are calculated only on the server.
- Colours, radii, shadows and fonts come only from `frontend/shared/src/styles/tokens.css` (classes like `bg-surface`, `text-muted`, `bg-primary`; never raw palette classes). Build screens from `frontend/user-web/src/components/ui`. Glass/blur only over the map.
- The web app never decides availability, price or refund; it shows what the API returns. Realtime messages are never trusted: re-fetch from the API.
- Nominatim is called only when the user submits a search, never while typing.
- Show "unknown" or the "Approximate" tag instead of inventing values.
- Follow existing patterns: the feature-folder layout, `AppError` codes, `useApiQuery`, the shared component library.
- Local development uses the live Supabase database (`DATABASE_URL`) by design (it is free, so there is no separate dev database); be careful with scripts that write. The tests use a separate throwaway database. Nothing is deployed: this is the development phase.

## Environment

- `backend/.env` (see `backend/.env.example`, every variable documented). Required: `DATABASE_URL`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `FRONTEND_URL`. The API refuses to start without them. For bookings and payments: `OTP_SECRET`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (an endpoint that needs a missing one answers 503). Tests/tooling: `TEST_DATABASE_URL`, `OCM_API_KEY`, `IMPORT_REGION`, `LEGACY_DATABASE_URL`, `DEMO_PASSWORD`.
- `frontend/user-web/.env`: `VITE_API_URL`, `VITE_GOOGLE_CLIENT_ID` (must equal the API's `GOOGLE_CLIENT_ID`), `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (must belong to the **same** Supabase project as the database, or live updates fall back to polling).
- Setup in detail: `docs/setup.md`.
