# ChargeSpot: what it does, what is built, what is not

Everything here comes from the code and the plan in `docs/phases.md`. Where the code does not say, it says **TODO: confirm with me**. Status as of 2026-10-22 (Phases 0 to 5 are on `main`; the Phase 6 work is on branch `phase-6-kiosk`, tested but not yet committed or approved).

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

### The station kiosk (Phase 6, `frontend/kiosk/`)
- A shared tablet app: a status board (every charger's state, kW, price, "free until", charging progress, walk-in money used), no names, phone numbers or bills of app users; sets itself up once with a pasted device key; goes back to the board after 30 seconds without a touch; a gentle "attract" loop after 2 minutes; a "Connection lost" cover that goes away by itself.
- **Start with a code:** a number pad for the 6-digit booking code; the server checks it for this station and its time window and starts that booking's charger; "Wrong code, 3 tries left"; 5 wrong tries in a row start a 2-minute wait; 20 wrong in 10 minutes raise an admin alert (`admin_alerts`).
- **Walk-in:** pick a free charger, pick ₹100 / ₹200 / ₹500 or "until the next booking" (each with its kWh), scan the Razorpay payment-link QR with any UPI app (3-minute hold, countdown); charging starts once Razorpay confirms; the tile later shows "Done · used ₹186 · ₹14 refunded". Charging stops when the money is used up, 5 minutes before the next booking, or at the end of the window; the unused money is recorded as a refund.
- Device keys (`ks_<prefix>_<secret>`, hashed in the database, one device = one station) made with `python -m scripts.make_kiosk_key` or `POST /api/admin/stations/{id}/devices`. Staff steps and a manual test script: `docs/kiosk.md`.

### Paying the energy bill
- "Pay ₹X" on the charging summary and on the Payment due tab opens Razorpay Checkout (test mode); the server verifies the signature and marks the bill paid; success, decline and closing the window are handled. The Explore/station banner says "Clear ₹X to book again" while a bill is due.
- Receipt page for a charging session (`/receipts/session/:id`): station, charger, times, kWh, rate, total, payment id, "Paid ✓", with Print / Save as PDF through the browser.

### Data
- Gujarat stations from Open Charge Map and OpenStreetMap plus 10 hand-verified Ahmedabad ones, cleaned and de-duplicated; missing chargers/power/prices/ratings generated and labelled; demo accounts, a week of demo bookings and kiosk device rows (`database/`). Details in `docs/data.md`.

### Engineering
- Backend tests 638, database tests 125, web unit tests 17, kiosk 15 + shared 40 (run on 2026-10-22); `npm run build` type-checks; `npm run lint`.
- A design system ("Midnight Charge", `docs/ui-flow.md`) with a component library and a development-only style guide at `/dev/ui`.

## Planned or half-built

| Item | Evidence in the code | State |
|---|---|---|
| **Real refunds through Razorpay** | `cancel()` and `_refund_in_full()` record the refund on the booking and payment only; no call to Razorpay's refund API. | Recorded only (test mode) |
| **Razorpay webhook** | `POST /api/payments/webhook` handles `payment.captured`, `order.paid` and `payment_link.paid` and is tested, but no webhook is registered (needs a public URL). Until then walk-ins are confirmed by the kiosk asking Razorpay about the payment link. | Waiting for deployment |
| **Admin area** (`/admin`) | `require_admin` and admin-only endpoints exist (create station, simulate, start, kiosk keys). No admin pages, reports, alerts list or operator settlement. | Not started (Phase 7) |
| **Deployment** (Render, Vercel), **CI** (GitHub Actions) | No deploy config, Dockerfile or workflow in the repo. | Not started (Phase 7) |
| **Final README, demo script, booking-flow docs** | `README.md` says "the full README arrives in Phase 7". | Not started |
| **Two-wheeler section** | Stations tagged `TWO_WHEELER` are stored and hidden everywhere (`vehicle_category = 'FOUR_WHEELER'` filter). | Data kept, no UI |
| **Phone number, email verification, password reset** | `users.phone` exists but no code reads or writes it. No verification or reset flow found. | Wanted by the owner; not started. Email and SMS services are not free, so ask before choosing one |
| **Admin "simulate external session" button** | Only the API and the command line exist. | API only |
| **Kiosk on a real tablet; kiosk Realtime** | Checked in desktop Chrome at 1280 x 800 and 1024 x 768 only. The kiosk polls the API every 2 to 4 seconds instead of using Supabase Realtime. | Owner's check pending |

## Known limitations (from the code)

- Charger power and price for many stations are generated, not real (`data_source = 'synthetic'`).
- Demo bookings end on 2026-10-16: with nothing upcoming, the demo data needs a refresh (`python -m database.pipeline`) before showing the project.
- Local development writes to the real Supabase database (`DATABASE_URL`); only the tests use a throwaway database.
- The default start charge (20%) and battery size (40 kWh) are assumptions when a booking has no vehicle (`CHARGING_RULES`).
- Opening hours are parsed from OpenStreetMap text; text the parser cannot read is treated as unknown (`features/stations/opening_hours.py`).
