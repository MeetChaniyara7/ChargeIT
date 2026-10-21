# Plan and status

Based on the state of the code on 2026-10-21 and the phase plan in `docs/phases.md` (which has the full task lists and prompts). Each phase ends with the owner's review; the next one starts only after approval.

## Done

- [x] **Phase 0: Planning and audit.** `docs/architecture.md`, `docs/phases.md`, decisions on payments, refunds, walk-ins, kiosk. (commit `fc3190e`)
- [x] **Phase 1: Restructure and secure the API.** `backend/`, `frontend/`, `database/`, `docs/`; config from environment variables; one error format; JWT auth fixes; npm workspaces. (`0074ad2`)
- [x] **Phase 2: Database.** 9 numbered migrations, the no-double-booking constraint, the status-change trigger, row-level security; Gujarat station import, cleaning, de-duplication; synthetic and demo data; saved queries. (`8fc6009`)
- [x] **UI pass.** "Midnight Charge" design tokens, component library, app shell, landing, sign in/up, profile shell. (`1fb5b74`)
- [x] **Phase 3: Discovery.** Station search by area/radius, 30-minute availability, recommendations (OSRM + fallback), geocoding with cache, Explore (map, list, sheet), station page. (`73b50e3`)
  - [x] **3.10 Smart search.** `parseSearch`, `/api/search/suggest` with `pg_trgm` (migration 010), accessible combobox, recent searches, "show without <filter>".
- [x] **Phase 4: Booking and payments.** State machine, one-time codes, refunds, holds with lazy expiry, "just taken" alternatives, Razorpay order/verify/webhook, instant booking, vehicles; slot picker, hold & pay, ticket, bookings, receipt, vehicles screens. Concurrency test (two connections, one winner). (`a0d0986`, pushed to `main`)

## In progress

- [ ] **Phase 5: Background jobs, simulator, realtime, live charging.** Built and tested; **not committed yet** (branch `phase-5-jobs-realtime`), waiting for the owner's review.
  - [x] Migrations 011 (jobs, energy formula, simulator), 012 (pg_cron), 013 (realtime nudges): **applied to Supabase**; `pg_cron` has run every minute without failures.
  - [x] Sessions API (`/api/me/sessions/...`), charger simulator (`/api/admin/...`), lazy checks (`features/jobs/lazy.py`), `BUSY_EXTERNAL` blocks, booking notices.
  - [x] Web: live charging page, Charging tab and app-bar pill, live updates with change flashes, reconnecting banner, moved/cancelled notices with alternatives.
  - [x] Tests: backend 555, database 119 (32 for the jobs), web 17, shared 40; Python and SQL energy formulas agree on 20,000 random cases.
  - [x] Realtime verified against the real Supabase project from Node: a charger change reached a subscriber in about 0.9 s.
  - [ ] Owner's check in a browser: two browsers on one station page updating together; the live charging page at 375, 768 and 1280 px; the manual test script in the Phase 5 summary.
  - [ ] Commit and merge the branch (owner decides).

## Not started

- [ ] **Phase 6: Kiosk and energy billing.** `frontend/kiosk/`; device keys (`POST /admin/stations/{id}/devices`, `X-Device-Key`); `app/features/kiosk/` (status, OTP start with 5-tries cooldown, walk-ins, payment-link webhook); walk-in settlement; `POST /me/sessions/{id}/pay`; Pay button, "Pending payment" section, receipts for sessions. Needs `qrcode.react` (already approved).
- [ ] **Phase 7: Admin, hardening, docs, deployment.** `/admin` pages (stations, chargers, kiosks, simulator panel, alerts, reports, operator settlement); edge-case tests; GitHub Actions CI; final README, `docs/booking-flow.md`, demo script; deploy to Render (API) and Vercel (web, kiosk); register the Razorpay webhook; Google OAuth production URLs; jury rehearsal.

## Loose ends (not in a phase)

- [ ] Refresh the demo data (all demo bookings ended on 2026-10-16): `python -m database.pipeline`. Check first that it keeps bookings made by hand.
- [ ] Commit the deletion of `project_review_report.txt` (deleted from disk at the owner's request; it is still in git history and on GitHub until committed).
- [ ] **Account features wanted by the owner (not started, no phase yet):** phone number, email verification, password reset. Collecting a phone number needs no outside service. Email verification and password reset need a way to send email, and SMS verification of a phone is not free, so **ask before choosing a service**.
- [ ] Decide the station-operator login flow (a proposal was given in chat; nothing decided yet).
- [ ] Old local branches (`phase-1-restructure`, `phase-2-database`, `phase-3-discovery`, `phase-4-booking`, `ui-foundation`, `fix/station-loading-and-auth-deps`) can be deleted once merged; `phase-3-discovery` and `phase-4-booking` already point into `main`.
- [ ] Optional front-end tests with `vitest` are mentioned in Phase 7; today the web unit tests use Node's built-in runner (no new dependency).
