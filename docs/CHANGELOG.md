# Changelog

Newest first. Dates are from the git history; commit hashes are given where there is a commit.

## 2026-10-21: Initial documentation added

Added by analysing the code (no source code was changed):

- `CLAUDE.md` rewritten to be shorter, with a pointer to read `docs/FLOW.md` and `docs/architecture.md` before structural changes, and a full command list (install, run, build, test, database, demo tools).
- `docs/FLOW.md`: how requests, sign-in, search, booking, payment, jobs, charging and realtime work, with real files and functions.
- `docs/architecture.md` section 18: what is built today, with a diagram (first written as a separate file, then merged into the planning document at the owner's request; the old job-migration numbers in `docs/phases.md` were corrected to `011`, `012`, `013`).
- `project_review_report.txt` (an old "VoltPulse" report) deleted from the repository root at the owner's request; the deletion is not committed yet.
- `docs/SCHEMA.md`: every table, column, constraint, index, trigger and function, generated from a database with all 13 migrations applied.
- `docs/API.md`: every endpoint, generated from the app's OpenAPI spec, plus all error codes.
- `docs/SPEC.md`, `docs/PLAN.md`, `docs/DECISIONS.md`, and this file.

### Owner decisions recorded on this date

- Nothing is deployed; the project is in the development phase only.
- Local development keeps using the one free Supabase database; there is no separate dev database.
- The single `chargespot-jobs` cron entry stays.
- Wanted next for accounts: phone number, email verification, password reset (not started; see `docs/PLAN.md`).

### State of the project on this date

- **Phases 0 to 4, the UI pass and the smart search are done** and on `main` (latest commit `a0d0986`, pushed to `origin`).
- **Phase 5 is built and tested but not committed** (branch `phase-5-jobs-realtime`): background jobs, charger simulator, realtime nudges, live charging page. Migrations `011` to `013` are applied to Supabase and `pg_cron` runs `run_due_jobs()` every minute (about 9,800 runs without a failure by 2026-10-21).
- **Tests:** backend 555, database 119, web 17, shared 40; `npm run build` and `npm run lint` clean (two old warnings in `AuthContext.tsx`).
- **Not built yet:** the kiosk app and OTP start, walk-ins, paying the energy bill, the admin area, CI, deployment, the final README (Phases 6 and 7).
- **Database (Supabase) on 2026-10-14:** 84 stations, 166 chargers, 20 users. All demo bookings have since ended (last on 2026-10-16).

## Earlier history (from git)

| Date | Commit | Change |
|---|---|---|
| 2026-10-12 | `a0d0986` | **Phase 4:** bookings, Razorpay test payments, vehicles and the booking screens |
| 2026-10-11 | `73b50e3` | **Phase 3:** station discovery, availability, recommendations and smart search |
| 2026-10-11 | `1fb5b74` | **UI pass:** "Midnight Charge" design system, component library, app shell |
| 2026-10-10 | `c2c9a67` | Merge of the new Chargespot repository's initial commit |
| 2026-10-10 | `0ef6465` | UI direction, screen flow and UI prompts |
| 2026-10-10 | `8fc6009` | **Phase 2:** Supabase schema, Gujarat station import, synthetic and demo data |
| 2026-10-10 | `2a07fad` | Initial commit (new repository) |
| 2026-10-10 | `0074ad2` | **Phase 1:** restructure into `backend/`, `frontend/`, `database/`; secure API skeleton |
| 2026-10-10 | `fc3190e` | Architecture and phase plan documents (Phase 0) |
| 2026-10-10 | `253f934` | Fix station loading against the current database schema; missing auth dependencies |
| 2026-08-21 | `ad08b35` | Initial commit of the original project (single FastAPI file and a React dashboard) |

Between the Phase 4 commit and now, the Phase 5 files, the new migrations and the `backend/scripts/` helpers are uncommitted.
