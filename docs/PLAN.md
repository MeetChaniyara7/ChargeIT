# Plan and status

Based on the state of the code on 2026-10-22 and the phase plan in `docs/phases.md` (which has the full task lists and prompts). Each phase ends with the owner's review; the next one starts only after approval.

## Done

- [x] **Phase 0: Planning and audit.** `docs/architecture.md`, `docs/phases.md`, decisions on payments, refunds, walk-ins, kiosk. (commit `fc3190e`)
- [x] **Phase 1: Restructure and secure the API.** `backend/`, `frontend/`, `database/`, `docs/`; config from environment variables; one error format; JWT auth fixes; npm workspaces. (`0074ad2`)
- [x] **Phase 2: Database.** 9 numbered migrations, the no-double-booking constraint, the status-change trigger, row-level security; Gujarat station import, cleaning, de-duplication; synthetic and demo data; saved queries. (`8fc6009`)
- [x] **UI pass.** "Midnight Charge" design tokens, component library, app shell, landing, sign in/up, profile shell. (`1fb5b74`)
- [x] **Phase 3: Discovery.** Station search by area/radius, 30-minute availability, recommendations (OSRM + fallback), geocoding with cache, Explore (map, list, sheet), station page. (`73b50e3`)
  - [x] **3.10 Smart search.** `parseSearch`, `/api/search/suggest` with `pg_trgm` (migration 010), accessible combobox, recent searches, "show without <filter>".
- [x] **Phase 4: Booking and payments.** State machine, one-time codes, refunds, holds with lazy expiry, "just taken" alternatives, Razorpay order/verify/webhook, instant booking, vehicles; slot picker, hold & pay, ticket, bookings, receipt, vehicles screens. Concurrency test (two connections, one winner). (`a0d0986`, pushed to `main`)

## In progress

- [x] **Phase 5: Background jobs, simulator, realtime, live charging.** Committed and on `main` (`3f85b1e`, with the documentation set): migrations 011 to 013 applied to Supabase, jobs on `pg_cron`, simulator, live charging page, realtime nudges. The owner's manual browser check (two browsers on one station page) is still open.

- [x] **Phase 6: Station kiosk and energy billing.** Committed and merged to `main` (`b8e636a`), pushed to GitHub. Not yet done: paying a walk-in QR with a phone in Razorpay's test page, a run on a real tablet, the owner's manual test script (`docs/kiosk.md`).

## Not started

- [ ] **Phase 7: Admin, hardening, docs, deployment.** In progress on branch `phase-7-release`, in the order of the plan: **(a) admin area and edge cases: built and tested, waiting for the owner** (migrations 015 and 016, `features/admin/`, the admin's own screen with users and roles, operators, kiosk keys, payments and an activity log, error/404/offline pages, accessibility and responsive audit: `docs/audit.md`); (b) tests and CI, (c) documentation and demo script, (d) deployment, (e) final clean-up: not started.

## Loose ends (not in a phase)

- [ ] A test **outside session** has been running on Tata Power - Riya Autolink Sola `CCS2-1` since 2026-10-21 03:34 UTC (left from a Phase 5 manual check). It blocks that charger for the demo: `python -m scripts.simulate event UNPLUG "Riya Autolink Sola" CCS2-1` ends it.
- [ ] The live database has a demo kiosk ("Demo kiosk" at Tata Power - Riya Autolink) and test sessions/payments from the Phase 6 live check.
- [ ] Refresh the demo data (all demo bookings ended on 2026-10-16): `python -m database.pipeline`. Check first that it keeps bookings made by hand.
- [ ] Commit the deletion of `project_review_report.txt` (deleted from disk at the owner's request; it is still in git history and on GitHub until committed).
- [ ] **Account features wanted by the owner (not started, no phase yet):** phone number, email verification, password reset. Collecting a phone number needs no outside service. Email verification and password reset need a way to send email, and SMS verification of a phone is not free, so **ask before choosing a service**.
- [ ] Decide the station-operator login flow (a proposal was given in chat; nothing decided yet).
- [ ] Old local branches (`phase-1-restructure`, `phase-2-database`, `phase-3-discovery`, `phase-4-booking`, `ui-foundation`, `fix/station-loading-and-auth-deps`) can be deleted once merged; `phase-3-discovery` and `phase-4-booking` already point into `main`.
- [ ] Optional front-end tests with `vitest` are mentioned in Phase 7; today the web unit tests use Node's built-in runner (no new dependency).
