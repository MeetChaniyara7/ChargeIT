# ChargeSpot

**BookMyShow for EV charging.** Find nearby charging stations, see which chargers are free, reserve a time slot, and start charging at the station with a one-time code.

> Capstone (college final-year) project, built only with free tools and services. The full README (screenshots, team roles, demo) arrives in Phase 7.

## Documentation

| Document | What's in it |
|---|---|
| [docs/architecture.md](docs/architecture.md) | What we are building and why: system design, data model, booking rules, payments, kiosk |
| [docs/phases.md](docs/phases.md) | The build plan, phase by phase, with tasks and acceptance checks |
| [docs/setup.md](docs/setup.md) | How to install, configure and run everything locally |

## Quick start

```bash
npm install                                  # web app + shared package
cd backend && python -m venv .venv          # then activate it (see docs/setup.md)
pip install -r requirements-dev.txt
```

Create `backend/.env` and `frontend/user-web/.env` from their `.env.example` files, then:

```bash
# terminal 1, in backend with the venv active
uvicorn app.main:app --reload --port 8000

# terminal 2, in the repository root
npm run dev:web
```

Open http://localhost:5173.

## Repository layout

```
backend/              FastAPI API (Python)
frontend/user-web/    React + Vite web app for drivers
frontend/kiosk/       Station kiosk app (from Phase 6)
frontend/shared/      Shared constants, formatters, generated API types
database/             Migrations, seeds, station imports, saved SQL queries
docs/                 Architecture, phase plan, setup guide
```

## Data attribution

Map data and tiles © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
