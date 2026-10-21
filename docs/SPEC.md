# ChargeSpot: what it does, what is built, what is not

Everything here comes from the code and the plan in `docs/phases.md`. Where the code does not say, it says **TODO: confirm with me**. Status as of 2026-10-21 (the Phase 5 work is on branch `phase-5-jobs-realtime`, tested but not yet committed).

## What the project is

ChargeSpot is "BookMyShow for EV charging" (a college final-year project, free tools only). Drivers find charging stations in Gujarat on a map, see which chargers are free for each 30-minute slot, hold a slot, pay a ₹199 booking fee (Razorpay **test mode**), get a one-time code, and (planned) enter it on a shared kiosk at the station to start charging. They then watch charging live and (planned) pay for the energy they used in the app. Walk-in drivers without a booking are meant to use the kiosk and pay by QR (planned).

**Users:** drivers (role `USER`) and admins (role `ADMIN`). There is no separate operator account in the code. Whether station operators get their own login is still being decided (see `docs/PLAN.md`).

**Money rules (in `backend/app/config.py`, `BOOKING_RULES`):** slot 30 minutes, 1 to 4 slots per booking, book up to 7 days ahead, 5-minute payment hold, ₹199 booking fee for app bookings (none for "Charge now"), code valid from 15 minutes before the start to 10 minutes after, no-show after 10 minutes (fee kept), refund tiers 100% / 75% / 50% / 0% at 2 hours / 30 minutes / 15 minutes before the start.

## Built

### Accounts
- Register and sign in with email and password (bcrypt); sign in with Google (ID-token button and redirect fallback); JWT in `localStorage`; sign out; profile page. (`features/auth/`, `frontend/user-web/src/features/auth/`)
- Return to the page you were heading to after signing in.

### Discovering stations
- Map and list of stations (Leaflet + OpenStreetMap), loaded only for the area on screen, starting in Ahmedabad. Pins show the number of free chargers.
- Filters (plug type chips, fast 50 kW+, open now, plus min kW, max price, operator from typed searches); held in the page URL so a view can be shared.
- Smart search box: understands plug types, kW, "fast", "open now", price, "near me", "near <place>", suggests stations, operators and cities from our own database with typo tolerance (`pg_trgm`), looks up places (Nominatim, cached, only on Enter), recent searches, "did you mean", "show without <filter>" when nothing matches.
- "Best for you now": top 5 stations with a reason ("2 CCS2 chargers free · 1.2 km · 60 kW"), using real road times from OSRM with a straight-line fallback.
- Station page: details, opening hours (open / closed / unknown, never guessed), rating, Navigate (Google Maps link), Share, charger cards, a 7-day 30-minute grid.
- Honest data: values generated or estimated carry an "Approximate" tag; unknown values show a dash.

### Booking and paying
- Select 1 to 4 adjacent free blocks on one charger by tap, drag or keyboard; clear reasons when a pick is not allowed; the pick survives a refresh.
- Summary bar with the ₹199 fee and an estimated energy cost (power, price, the default vehicle's battery).
- Hold for 5 minutes (countdown from the server's clock), pay with Razorpay Checkout (test mode), the server verifies the signature, then the booking is confirmed and a 6-digit code is shown **once**. A payment that arrives after the hold ran out re-books the slot if it is free, otherwise it is refunded in full.
- "Just taken" sheet with alternatives (other times, other chargers, nearby stations) when someone else got the slot first.
- Ticket page (movie-ticket style, code tiles, add to calendar as an `.ics` file, navigate).
- "Charge now" on a free charger: no fee, up to 2 hours (or until the next booking minus 5 minutes).
- My bookings (Upcoming, Past, Payment due): status timeline, cancel with the refund shown first, show a new code (the old one stops working), receipt page.
- Vehicles: add, edit, delete, default; the default sets the plug filter and the cost estimate.
- Unpaid energy bills block new bookings.

### Charging and live updates
- Charging sessions with live energy, battery %, cost so far and time left (one formula in Python and SQL, tested equal); stop with a confirm sheet; a summary with the bill; a warning in the last 5 minutes; automatic stop at the end of the slot.
- Charging tab and an app-bar "Charging · 68%" pill; a "Reconnecting..." banner when live updates drop (then 30-second polling).
- Live updates (Supabase Realtime nudges, then re-fetch from the API) for the station grid, map pins, bookings list, ticket and charging page, with a brief flash on what changed.
- Charger situations: a booking is **moved** to another free charger (notice and toast), the driver is **warned** when an outside driver is still charging, or the booking is **cancelled with a full refund** and three nearby alternatives are shown.

### Running by itself
- SQL jobs (`database/migrations/011_jobs.sql`) run every minute through `pg_cron` on Supabase and lazily inside the API: expire holds, mark no-shows, resolve occupied starts, auto-stop sessions, reserve chargers 15 minutes ahead.
- Charger simulator (`simulate_charger_event`, admin endpoint, and `backend/scripts/simulate.py`): outside start (refused while reserved), outside stop, unplug, fault, recover; every event logged.

### Data
- Gujarat stations from Open Charge Map and OpenStreetMap plus 10 hand-verified Ahmedabad ones, cleaned and de-duplicated; missing chargers/power/prices/ratings generated and labelled; demo accounts, a week of demo bookings and kiosk device rows (`database/`). Details in `docs/data.md`.

### Engineering
- Backend tests 555, database tests 119, web unit tests 17 + shared 40 (run on 2026-10-21); `npm run build` type-checks; `npm run lint`.
- A design system ("Midnight Charge", `docs/ui-flow.md`) with a component library and a development-only style guide at `/dev/ui`.

## Planned or half-built

| Item | Evidence in the code | State |
|---|---|---|
| **Station kiosk app** (status board, OTP start, walk-in QR) | `frontend/kiosk/` does not exist. Tables `station_devices` and `otp_attempts` exist (migration 005) and demo kiosk rows are seeded, but no API reads them. `features/charging/service.py` says starting a session is "what the kiosk does (Phase 6)". | Not started (Phase 6) |
| **Start charging with the code** | Nothing checks a typed code today. `otp.matches()` and `is_valid_now()` exist, unused by any route. The admin tool `POST /api/admin/bookings/{id}/start` and `scripts/simulate.py start` stand in. | Half-built |
| **Walk-in bookings** (`source = 'WALK_IN'`) | Allowed by the database transitions, handled in `auto_stop_sessions` and `finish_session` (`PREPAID_SETTLED`), `walkin_*` rules in `BOOKING_RULES`. No endpoint or screen creates one. | Database side only |
| **Paying the energy bill** | Sessions get `bill_amount` and `bill_status = 'DUE'`; `payments.purpose` allows `ENERGY`; `SessionSummary.tsx` has a disabled Pay button ("arrives in the next update"); the "Payment due" tab only lists bills. There is no `POST /me/sessions/{id}/pay`. | Half-built (Phase 6) |
| **Real refunds through Razorpay** | `cancel()` and `_refund_in_full()` record the refund on the booking and payment only; no call to Razorpay's refund API. | Recorded only (test mode) |
| **Razorpay webhook** | `POST /api/payments/webhook` is implemented and tested, but no webhook is registered (needs a public URL). | Waiting for deployment |
| **Admin area** (`/admin`) | `require_admin` and three admin-only endpoints exist (`POST /api/stations`, simulate, start). No admin pages, reports, kiosk-key management or alerts. | Not started (Phase 7) |
| **Deployment** (Render, Vercel), **CI** (GitHub Actions) | No deploy config, Dockerfile or workflow in the repo. | Not started (Phase 7) |
| **Final README, demo script, booking-flow docs** | `README.md` says "the full README arrives in Phase 7". | Not started |
| **Two-wheeler section** | Stations tagged `TWO_WHEELER` are stored and hidden everywhere (`vehicle_category = 'FOUR_WHEELER'` filter). | Data kept, no UI |
| **Phone number, email verification, password reset** | `users.phone` exists but no code reads or writes it. No verification or reset flow found. | Wanted by the owner; not started. Email and SMS services are not free, so ask before choosing one |
| **Admin "simulate external session" button** | Only the API and the command line exist. | API only |

## Known limitations (from the code)

- Charger power and price for many stations are generated, not real (`data_source = 'synthetic'`).
- Demo bookings end on 2026-10-16: with nothing upcoming, the demo data needs a refresh (`python -m database.pipeline`) before showing the project.
- Local development writes to the real Supabase database (`DATABASE_URL`); only the tests use a throwaway database.
- The default start charge (20%) and battery size (40 kWh) are assumptions when a booking has no vehicle (`CHARGING_RULES`).
- Opening hours are parsed from OpenStreetMap text; text the parser cannot read is treated as unknown (`features/stations/opening_hours.py`).
