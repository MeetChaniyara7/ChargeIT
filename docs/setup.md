# ChargeSpot: Local Setup

How to run ChargeSpot on your own computer. Commands assume you are in the repository root (`ChargeIT/`) unless a step says otherwise.

## 1. Prerequisites

| Tool | Version | Check with |
|---|---|---|
| Node.js | 20 or newer (we use 24) | `node -v` |
| npm | 10 or newer | `npm -v` |
| Python | 3.12 | `python --version` |
| Supabase project | free tier, region Mumbai | the team shares one; ask for the connection string |
| PostgreSQL (local) | 15 or newer, only for running the database tests | `psql --version` |
| Git | any recent | `git --version` |

## 2. Repository layout

```
backend/              FastAPI API (Python)
frontend/user-web/    React web app for drivers (and admins)
frontend/kiosk/       Station kiosk app (from Phase 6)
frontend/shared/      Constants, formatting helpers and API types shared by the front ends
database/             Migrations, seeds, import scripts, saved SQL queries (from Phase 2)
docs/                 Architecture, phase plan, this guide
data/                 Raw downloads and old exports (git-ignored, not needed to run)
```

See [architecture.md, section 4](architecture.md#4-folder-structure) for the full tree. The JavaScript parts are an **npm workspaces** monorepo: one `npm install` at the root installs everything. The API is a separate Python project with its own virtual environment.

## 3. API (`backend`)

### Install (first time)

```bash
cd backend
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate          # Windows (cmd / PowerShell)
source .venv/bin/activate       # macOS / Linux

pip install -r requirements-dev.txt
```

### Configure

Copy `backend/.env.example` to `backend/.env` and fill it in. Every variable is explained in the example file. The API **refuses to start** if a required value is missing:

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | Supabase **Session pooler** connection string (see section 4) |
| `JWT_SECRET_KEY` | yes | Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `GOOGLE_CLIENT_ID` | yes | Same value as the web app's `VITE_GOOGLE_CLIENT_ID` |
| `FRONTEND_URL` | yes | `http://localhost:5173` locally |
| `CORS_ORIGINS` | no | Defaults to `FRONTEND_URL` |
| `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | no | Only for the Google redirect sign-in fallback |

Ask a teammate for the shared Google client ID. **Never commit `.env` files.**

### Run

```bash
# from backend, with the virtual environment active
uvicorn app.main:app --reload --port 8000
```

- Health check: http://localhost:8000/health
- Interactive API docs: http://localhost:8000/docs

Or, from the repository root (virtual environment still active): `npm run dev:api`.

### Test

```bash
# from backend, with the virtual environment active
python -m pytest
```

Or from the root: `npm run test:api`. The API tests do **not** need a database.

## 4. Database (`database/`)

The database runs on **Supabase** (free PostgreSQL). Everything in `database/` is run from the **repository root** with the backend's virtual environment active, because the scripts use the same Python packages as the API.

### Connect to Supabase (once per computer)

1. In the Supabase dashboard, open the project, click **Connect**, and copy the **Session pooler** URI. Don't use the "Direct connection": it only works over IPv6.
2. Change `postgresql://` at the start to `postgresql+psycopg://`.
3. Replace `[YOUR-PASSWORD]`, **including the square brackets**, with the database password. If it contains `@ : / # % ?`, URL-encode them (`@` → `%40`).
4. Put the result in `backend/.env` as `DATABASE_URL`.

### Build or update the database

```bash
# repository root, backend venv active
python -m database.pipeline
```

This runs every step in order, and each step is safe to re-run:

| Step | What it does |
|---|---|
| 1. migrate | Creates or upgrades the schema from `database/migrations/*.sql` |
| 2. users | Copies accounts from the old local database (only if `LEGACY_DATABASE_URL` is set) |
| 3. manual | Imports the 10 hand-verified Ahmedabad stations from `data/legacy/` |
| 4. osm | Imports OpenStreetMap stations for the region |
| 5. ocm | Imports Open Charge Map stations (needs `OCM_API_KEY`) |
| 6. dedupe | Merges duplicate stations; report in `data/raw/dedupe_report.csv` |
| 7. synthetic | Fills missing chargers, power, prices and ratings (labelled as estimates) |
| 8. demo | Demo accounts, a week of Ahmedabad bookings, kiosk devices |

Options: `--refresh` re-downloads station data (otherwise the cached files in `data/raw/` are used), and `--fresh-stations` deletes all stations and re-imports them (refused if real bookings exist).

The **demo password and kiosk keys are printed once**, at the end. Save them. If they're lost, re-issue them without touching anything else:

```bash
python -m database.seeds.demo_data --reset-password --new-kiosk-keys
```

Individual steps can also be run alone, e.g. `python -m database.migrate --status` or `python -m database.imports.dedupe --dry-run`.

### Saved queries

`database/queries/*.sql` are read-only reports (today's bookings, booking history, no-shows, data quality). Open them in DBeaver connected to Supabase, using the same host, user and password as `DATABASE_URL`.

### Database tests

The tests prove the booking rules hold: no double booking (including two people booking at the same instant), legal status changes only, row-level security on every table. They run against a **throwaway local database**, never Supabase:

```bash
# once: create an empty local database, e.g. in DBeaver or psql
CREATE DATABASE chargespot_test;
```

Set `TEST_DATABASE_URL` in `backend/.env` to point at it, then:

```bash
# repository root, backend venv active
python -m pytest database/tests
```

The tests wipe and rebuild `chargespot_test` on every run. Tests that need it are skipped when `TEST_DATABASE_URL` isn't set.

## 5. Web app (`frontend/user-web`)

### Install (first time)

```bash
# from the repository root
npm install
```

### Configure

Copy `frontend/user-web/.env.example` to `frontend/user-web/.env`:

| Variable | Required | Notes |
|---|---|---|
| `VITE_API_URL` | yes | `http://localhost:8000` locally |
| `VITE_GOOGLE_CLIENT_ID` | yes | Must match the API's `GOOGLE_CLIENT_ID` |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | from Phase 5 | Live updates only |

Everything starting with `VITE_` is visible in the browser, so never put secrets there.

### Run

```bash
# from the repository root
npm run dev:web
```

Open http://localhost:5173. The API must be running for login and the map to work.

### Build and lint

```bash
npm run build   # type-checks and builds every workspace
npm run lint    # oxlint
```

## 6. Shared API types

`frontend/shared/src/api-types.ts` is generated from the API's OpenAPI spec. After changing API endpoints, regenerate it **with the API running**:

```bash
npm run generate:api-types
```

This uses `npx openapi-typescript`, so nothing extra needs installing.

## 7. Everyday workflow

1. Terminal 1: `cd backend`, activate the venv, `uvicorn app.main:app --reload --port 8000`
2. Terminal 2: `npm run dev:web`
3. Before committing: `npm run build`, `npm run lint`, `python -m pytest` in `backend`, and `python -m pytest database/tests` from the root.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `MissingSettingError: Missing required environment variable(s)` | Fill in the named variable in `backend/.env` |
| Blank page; console says `VITE_API_URL is not set` | Create `frontend/user-web/.env` from the example |
| Google button missing or "invalid client" | `VITE_GOOGLE_CLIENT_ID` is empty or differs from the API's `GOOGLE_CLIENT_ID`, or `http://localhost:5173` isn't an authorised origin in Google Cloud Console |
| Map shows "Unable to load charging stations" | API not running, or `DATABASE_URL` is wrong |
| `ModuleNotFoundError` when starting the API | The virtual environment isn't active, or `pip install -r requirements-dev.txt` wasn't run |
| Browser reports a CORS error | Add the web app's URL to `CORS_ORIGINS` in `backend/.env` and restart the API |
| `password authentication failed` connecting to Supabase | The `[ ]` around the password are still in `DATABASE_URL`, the password is wrong, or it has unencoded special characters |
| `ModuleNotFoundError: No module named 'database'` | Run database commands from the **repository root**, not from `database/` |
| `npm run generate:api-types` produces old types | Another API is already running on port 8000; stop it, start the current one, and run again |
