# How the code works: end-to-end flows

Step-by-step sequences with the real files and functions involved. Paths are from the repository root. The API is in `backend/app/`, the web app in `frontend/user-web/src/`, shared code in `frontend/shared/src/`, SQL in `database/migrations/`.

Contents: [1 Startup](#1-startup) · [2 A request, end to end](#2-a-request-end-to-end) · [3 Sign in](#3-sign-in) · [4 Finding stations](#4-finding-stations-explore-and-search) · [5 Station page and availability](#5-station-page-and-availability) · [6 Booking and paying](#6-booking-and-paying) · [7 After booking](#7-after-booking-codes-cancel-charge-now) · [8 Background jobs](#8-background-jobs-and-lazy-checks) · [9 Charging sessions](#9-charging-sessions-and-the-simulator) · [10 Live updates](#10-live-updates-realtime) · [11 Building the database](#11-building-the-database)

Related: system picture in `docs/architecture.md` (section 18), tables in `docs/SCHEMA.md`, endpoints in `docs/API.md`.

---

## 1. Startup

**API** (`uvicorn app.main:app`)
1. `backend/app/main.py` runs `create_app()` at import time.
2. `get_settings()` (`backend/app/config.py`) reads environment variables (and `backend/.env` through `load_dotenv()`). It raises `MissingSettingError` if `DATABASE_URL`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID` or `FRONTEND_URL` is missing, so the server refuses to start. `OTP_SECRET` and `RAZORPAY_*` are optional at startup; `require_setting()` answers `503 SETTING_MISSING` when an endpoint needs one that is empty.
3. `setup_logging()` (`app/core/logging.py`), CORS middleware (origins from `CORS_ORIGINS`), and `register_error_handlers()` (`app/core/errors.py`).
4. Every feature's `router` is included, then `GET /health` is defined.
5. `app/db.py` creates the SQLAlchemy engine from `DATABASE_URL` but does not connect until the first query.

**Web app** (`npm run dev:web` → Vite)
1. `frontend/user-web/index.html` loads Google's sign-in script (`accounts.google.com/gsi/client`) and `src/main.tsx`, which calls `createRoot(...).render(...)` for `src/app/App.tsx`.
2. `App.tsx` wraps everything in `AuthProvider` and `ToastProvider`, then `BrowserRouter` with the route table (see `docs/architecture.md`, section 18).
3. `lib/api.ts` throws at import if `VITE_API_URL` is not set.
4. `AuthProvider` (`features/auth/AuthContext.tsx`) looks for a `#token=` in the URL hash (Google redirect flow), then calls `authService.getCurrentUser()` if a token is in `localStorage['token']`.

---

## 2. A request, end to end

Every call from the web app, for example "list my bookings":

1. A component calls `useApiQuery(key, fetcher)` (`lib/useApiQuery.ts`) with a fetcher that calls `apiFetch(path)` (`lib/api.ts`).
2. `apiFetch` adds `Authorization: Bearer <token>` from `tokenStorage`, sends `fetch(API_URL + path)`, and parses the JSON.
3. On the server, FastAPI matches the route in a feature's `router.py` (for example `features/bookings/router.py` → `my_bookings`).
4. Dependencies run first: `get_db()` (`app/db.py`) opens one SQLAlchemy `Session` per request; `get_current_user()` (`features/auth/dependencies.py`) reads the bearer token, `decode_access_token()` checks the signature and expiry, then loads the `User`. `require_admin()` adds a role check.
5. The router calls a **service** function (`features/bookings/service.py` → `my_bookings`), which holds the rules and calls the database through SQLAlchemy models, the `repository.py` of the feature, or raw `text()` SQL for the job functions.
6. The service returns Pydantic models (`schemas.py`); the router's `response_model` serialises them.
7. Errors: a service raises `AppError(status, code, message, details)`; `register_error_handlers()` turns it into `{"error": {"code", "message", "details"?}}`. Plain `HTTPException`s are mapped to a code by status. Validation errors become `422 VALIDATION_ERROR`. Anything unexpected becomes `500 INTERNAL_ERROR` (logged).
8. Back in `apiFetch`: a non-2xx response becomes an `ApiError(status, code, message, details)`. On `401` with a token it clears the token and dispatches the `chargespot:unauthorized` event; `AuthContext` listens and signs the user out. `useApiQuery` keeps the previous data while a new request runs, aborts stale requests, and exposes `retry()` (loading state) and `refresh()` (quiet).

---

## 3. Sign in

Three ways, all ending with the API's own JWT (HS256, `create_access_token()` in `features/auth/tokens.py`, claims `sub`, `email`, `role`) stored in `localStorage['token']`.

**Email and password**
1. `RegisterForm.tsx` / `LoginForm.tsx` call `authService.register()` / `login()` (`features/auth/authService.ts`) → `POST /auth/register` or `/auth/login`.
2. `register()` in `features/auth/router.py` lowercases the email, refuses duplicates (`400`), stores `hash_password()` (bcrypt, `passwords.py`), role `USER`. `login()` checks `verify_password()`.
3. Both return `token_response(user)` (`features/auth/service.py`): `{access_token, token_type, user}`.
4. `authService.signIn()` stores the token; `AuthContext` sets the user; `returnPathFrom()` (`features/auth/returnTo.ts`) sends the user back to the page they were heading to, else `/explore`.

**Google, ID-token flow** (used by the button)
1. `GoogleSignInButton.tsx` gets a Google credential in the browser (Google Identity Services, `VITE_GOOGLE_CLIENT_ID`).
2. `authService.loginWithGoogleCredential()` → `POST /api/auth/google` → `google_id_token_login()` → `verify_google_id_token()` (`features/auth/google.py`, checks the token against `GOOGLE_CLIENT_ID`).
3. `find_or_create_google_user()` finds the user by Google id, else links an existing account with the same email, else creates one. Returns `token_response()`.

**Google, redirect flow** (fallback)
1. `authService.loginWithGoogle()` sets `window.location` to `GET /auth/google/login` → `google_login_redirect()` makes a random `state`, stores it in an HttpOnly cookie (`chargespot_oauth_state`, 10 minutes) and redirects to Google.
2. Google redirects to `GET /auth/google/callback` → `google_callback()` compares `state` with the cookie (`secrets.compare_digest`), calls `exchange_code_for_google_user()`, then `find_or_create_google_user()`.
3. The API redirects to `FRONTEND_URL/login#token=<jwt>`; `AuthContext` reads the fragment, stores the token and cleans the URL.

**Protected pages**: `ProtectedRoute.tsx` shows a skeleton while `AuthContext` is loading, then either renders the page or redirects to `/login` with `state.from`.

---

## 4. Finding stations (Explore and search)

**Map and list**
1. `features/stations/ExplorePage.tsx` holds the map view, `useExploreFilters()` (filters live in the page URL: `connector`, `fast`, `min_kw`, `max_price`, `operator`, `open`, `q`), and the selected station.
2. `StationMap.tsx` (Leaflet) calls `onViewChange(bounds, view)` after the map stops moving. `exploreView.ts` saves the view in `sessionStorage`.
3. `useStations(bounds, reference, filters)` debounces by `MAP_SETTLE_MS` (400 ms), builds the URL with `stationsUrl()` (`stationsUrl.ts`) and calls `GET /api/stations?bbox=...&lat=...&lng=...`.
4. `features/stations/router.py` → `search_stations()` builds a `StationQuery`, then `service.search()` calls `repository.find_stations()` (one query for stations, a `selectinload` for chargers), `busy_right_now()` (`features/availability/occupancy.py`, one query) and `build_summary()` per station (free count, connector types, min/max power, min price, `is_open_now` from `opening_hours.is_open_now()`).
5. The default view is Ahmedabad (`DEFAULT_CENTER` in `features/stations/constants.ts`). The default vehicle's plug is put into the filter once per session (`VEHICLE_PREFILL_KEY` in `ExplorePage.tsx`).

**"Best for you now"**
1. `useRecommendations()` waits for the reference point to settle (800 ms, moved more than 1 km) → `GET /api/recommendations`.
2. `features/recommendations/service.py` → `recommend()`: finds stations within 15 km (`repository.find_stations`), `busy_charger_ids()` for the free window, one routing request through `osrm.travel_times.estimate()` (falls back to straight-line at 25 km/h), then `scoring.rank()` (pure functions) and `reason_text()`.

**Search box**
1. `SearchBox.tsx` (an ARIA combobox) calls `parseSearch(text)` (`frontend/shared/src/search.ts`, pure) to find filter words; the leftover text goes to `useSearchSuggest()` (250 ms debounce) → `GET /api/search/suggest`.
2. `features/search/service.py` → `suggest()`: `repository.find_stations()`, `find_operators()`, `find_cities()` (PostgreSQL `pg_trgm` from migration `010_search.sql`), `did_you_mean()`.
3. On Enter, `ExplorePage.submitSearch()` applies the parsed filters to the URL, then tries: a station name already on screen, then the suggest API (station, operator, city), and only then `useGeocode().search()` → `GET /api/geocode` → `features/geocoding/service.py` `geocode()`: normalises the query, reads/writes `geocode_cache`, otherwise calls Nominatim through a 1-request-per-second `RateLimiter`. Nominatim is never called while typing.

---

## 5. Station page and availability

1. `StationPage.tsx` (route `/stations/:stationId`) calls `useStationDetail()` → `GET /api/stations/{id}` (`service.detail()`) and `useAvailability(stationId, day)` → `GET /api/stations/{id}/availability?date=YYYY-MM-DD`.
2. `features/availability/service.py` → `station_availability()`:
   1. `check_date_in_range()` (yesterday to 7 days ahead).
   2. `run_due_jobs()` (`features/jobs/lazy.py`) for this station (see section 8).
   3. `bookings_overlapping()` (one query for the whole day), a query for running outside sessions, then `_state()` for each 30-minute block: `PAST`, `OUT_OF_SERVICE`, `BUSY_EXTERNAL`, `FREE`, `HELD` or `BOOKED`. `core/slots.py` (`day_blocks()`, IST helpers) makes the blocks.
3. `AvailabilityGrid.tsx` draws the grid and only displays server states. `selection.ts` (`chooseBlock()`, `dragBlocks()`, `dragPreview()`, pure) decides what a tap, drag or key press selects (1 to 4 adjacent free blocks on one charger) and which message to show when it is not allowed. `selectionStorage.ts` keeps the pick in `sessionStorage`.
4. `useRealtimeRefresh()` re-fetches both queries when the station changes (section 10); `useChanged()` flashes the blocks that changed.

---

## 6. Booking and paying

```
StationPage ──POST /api/bookings──▶ bookings.service.create_hold ──▶ bookings (HELD, 5 min)
   │                                          │ 23P01
   │                                          ▼
   │                               409 SLOT_TAKEN + alternatives (SlotTakenSheet)
   ▼
HoldPage ──POST /api/payments/orders──▶ payments.service.create_order ──▶ Razorpay order
   │
   ├─ openCheckout() (lib/razorpay.ts) ──▶ Razorpay Checkout in the browser
   └─ POST /api/payments/verify ──▶ payments.service.verify ──▶ confirm_payment ──▶ CONFIRMED + code
                                                                                      │
TicketPage ◀── navigate with the code in router state (shown once) ◀──────────────────┘
```

**6.1 Pick a slot.** `StationPage` keeps `selection` (charger, start, end, blocks). `SummaryBar.tsx` shows the fee (₹199, server decides) and an estimate from `estimateEnergy()` (`frontend/shared/src/estimate.ts`, uses the default vehicle's battery when its plug fits).

**6.2 Hold the slot.** "Hold & pay" calls `StationPage.hold()` → `POST /api/bookings {charger_id, start, blocks, vehicle_id?}` → `features/bookings/router.py` `create_booking()` → `service.create_hold()`:
1. Validation: `is_slot_aligned()`, start in the future and within 7 days, 1 to 4 blocks.
2. `_charger_for_booking()` (active four-wheeler station, charger not faulted/out of service), `run_due_jobs()` for the station, `_check_vehicle()`.
3. Inside a retry loop: `expire_stale_holds()` (frees this charger's and this user's expired holds in the same transaction), refuse if the user already has a live hold (`ACTIVE_HOLD_EXISTS`), `_check_no_dues()` (`UNPAID_BILL`).
4. `state_machine.check(None, "HELD", "APP")` and `set_actor()` (tells the trigger who and why), then insert a `Booking` (`HELD`, `hold_expires_at = now + 5 min`, `booking_fee = 199`) and `db.flush()`.
5. The database decides overlaps (`bookings_no_double_booking`, SQLSTATE `23P01`) → `_slot_taken()` builds `alternatives.build()` (other times on the same charger via `free_starts_near()`, other chargers with the same plug, nearby stations from `recommendations.service.recommend()`) and raises `AppError(409, "SLOT_TAKEN", details={alternatives})`. A deadlock (`40P01`) is retried once. The one-hold-per-user index (`bookings_one_hold_per_user`) gives `ACTIVE_HOLD_EXISTS`.
6. `StationPage` navigates to `/book/:bookingId`, or opens `SlotTakenSheet.tsx` (each alternative is held in one tap by calling `hold()` again).

**6.3 Pay.** `HoldPage.tsx` (`useBooking()`, `useHoldCountdown()` counts down from the server's `hold_expires_at - server_time`, so the phone's clock does not matter):
1. "Pay" → `POST /api/payments/orders` → `features/payments/service.py` `create_order()`: only a `HELD`, unexpired `APP` booking; re-uses an existing `CREATED` payment; otherwise `gateway.create_order()` (`RazorpayGateway`, amount = `booking_fee` x 100 paise, `receipt = booking_id`) and inserts a `Payment` (`CREATED`). Returns the public key id, `order_id`, amount and a Checkout timeout slightly under the hold.
2. `openCheckout()` (`lib/razorpay.ts`) loads Razorpay's script and opens Checkout. Result: `paid`, `failed` (declined) or `closed`.
3. `paid` → `POST /api/payments/verify {razorpay_order_id, razorpay_payment_id, razorpay_signature}` → `service.verify()`: `verify_payment_signature()` (HMAC-SHA256 of `order_id|payment_id` with `RAZORPAY_KEY_SECRET`; `400 INVALID_SIGNATURE` if wrong), lock the payment, check ownership, then `confirm_payment()`.
4. `confirm_payment()` (shared with the webhook, safe to run twice): payment `CAPTURED`; if the booking is still `HELD` (even if the hold just ran out) → `state_machine.transition(... "CONFIRMED")` and `bookings.service.issue_code()` (`otp.generate()` makes a 6-digit code unique among overlapping bookings at the station, stored only as an HMAC-SHA256 with `OTP_SECRET`). If the booking already `EXPIRED`, `_rebook_expired()` takes the same slot again when it is free; otherwise (or if cancelled, or the slot is over) `_refund_in_full()` records a full refund.
5. The code is returned **once** in `VerifyOut.otp`. `HoldPage` navigates to `/tickets/:bookingId` with the code in router state (`TicketState`); `TicketPage.tsx` copies it into memory and clears the history state, so a refresh does not show it again.
6. When the countdown reaches zero `HoldPage` asks the server again; the server's lazy expiry decides. "Release this slot" calls `POST /api/bookings/{id}/cancel`.

**6.4 Webhook (backup path).** `POST /api/payments/webhook` → `features/payments/router.py` `webhook()` reads the raw body → `service.handle_webhook()`: `verify_webhook_signature()` (`RAZORPAY_WEBHOOK_SECRET`), insert the event id into `webhook_events` (`ON CONFLICT DO NOTHING`; a repeat returns `duplicate`), and for `payment.captured` / `order.paid` call `confirm_payment()`. **The webhook URL is not registered in Razorpay yet** (it needs a public URL; planned for deployment), so today `/verify` is the only confirmation path.

---

## 7. After booking: codes, cancel, Charge now

- **List and read:** `GET /api/me/bookings?scope=upcoming|past` → `service.my_bookings()` (runs `run_for_stations()` first, one query for bookings, one for payments, one for session ids); `GET /api/bookings/{id}` → `get_booking()` (lazy jobs, then `expire_if_stale()`).
- **New code:** `BookingSheets.tsx` (`NewCodeSheet`) → `POST /api/bookings/{id}/otp` → `service.show_new_code()`: only `CONFIRMED`, unused, before `start + 10 min`; `issue_code()` replaces the stored hash, so the old code stops working.
- **Cancel:** `CancelSheet` first calls `GET /api/bookings/{id}/cancel-preview` → `_refund_for()` → `refunds.refund_for()` (pure: 100% at 2 hours or more, 75% at 30 minutes, 50% at 15 minutes, else 0; boundaries count for the driver). Confirm → `POST .../cancel` → `service.cancel()`: `state_machine.transition(... "CANCELLED")`, records `refund_amount` on the booking and on the payment (`REFUNDED` / `PARTIALLY_REFUNDED`). **Refunds are recorded, not sent to Razorpay** (test mode).
- **Charge now:** `ChargeNowSheet.tsx` → `POST /api/bookings/instant` → `service.create_instant()`: charger must be `AVAILABLE` or `RESERVED`, no live booking now, `instant.instant_window()` (now until the earlier of next booking minus 5 minutes or 2 hours, at least 15 minutes), inserts a `CONFIRMED` `INSTANT` booking with no fee and a code in the response.
- **Unpaid bills:** `GET /api/me/dues` → `unpaid_bills()` reads `charging_sessions` with `bill_status = 'DUE'`; while any exist `create_hold`/`create_instant` raise `UNPAID_BILL`, and `DuesBanner.tsx` disables booking.

All status changes go through `features/bookings/state_machine.py` (`transition()`), whose table equals `allowed_booking_transitions` in the database (a test compares them); the trigger `enforce_booking_transition` re-checks and writes `booking_events`.

---

## 8. Background jobs and lazy checks

Rules that must happen by themselves are SQL functions in `database/migrations/011_jobs.sql`. All take `p_now timestamptz DEFAULT now()` and an optional station.

`run_due_jobs(p_now, p_station)` runs, in this order:
1. `expire_holds()`: `HELD` with `hold_expires_at <= p_now` → `EXPIRED`.
2. `resolve_occupied_starts()`: a `CONFIRMED`, unclaimed booking whose slot has started and whose charger is faulted or running an outside session → move to a free charger with the same plug at the station (closest power), else cancel with a full refund of what was paid; sets `notice_kind` / `notice_text` on the booking.
3. `mark_no_shows()`: `CONFIRMED` and no code used 10 minutes after the start → `NO_SHOW` (fee kept).
4. `auto_stop_sessions()`: ends booking sessions at slot end (walk-in sessions: 5 minutes before the next booking or when the prepaid amount is used up) through `finish_session()`.
5. `apply_reservation_locks()`: chargers with a confirmed booking within 15 minutes become `RESERVED` (`apply_charger_event`), released when no longer needed; warns drivers when an outside session still occupies the charger.

Two callers:
- **pg_cron**: `database/migrations/012_cron.sql` enables `pg_cron` (Supabase) and schedules `chargespot-jobs` = `SELECT run_due_jobs()` every minute.
- **Lazy checks**: `features/jobs/lazy.py` `run_due_jobs(db, now, station_id)` runs the same function for one station before the API answers in `availability.service.station_availability`, `bookings.service` (`create_hold`, `create_instant`, `get_booking`, `my_bookings`) and `charging.service._load_fresh`. A failure is logged and rolled back; the read carries on. So correctness never depends on when cron last ran.

---

## 9. Charging sessions and the simulator

There is no kiosk yet, so charging is started by the admin demo tools (`backend/scripts/simulate.py`, or `POST /api/admin/bookings/{id}/start`).

1. **Start:** `features/charging/service.py` `start_session()`: booking must be `CONFIRMED`, charger `AVAILABLE` or `RESERVED`; `state_machine.transition(... "ACTIVE")`, marks the code used, inserts a `ChargingSession` (`start_soc_percent` = 20 by default), and runs `apply_charger_event(..., 'SESSION_START')` in SQL (charger → `CHARGING`, logged in `charger_events`).
2. **Live numbers:** `GET /api/me/sessions/{id}` → `get_session()` → `_load_fresh()` (lazy jobs) → `to_live()`: `energy.energy_kwh()` (power x hours x 0.9, capped by the vehicle's battery x remaining room; same formula as the SQL `session_energy_kwh`), `battery_percent()`, `bill_amount()`, `seconds_left`, `stop_warning` (last 5 minutes), `next_booking_waiting`.
3. **Web page:** `LiveChargingPage.tsx` uses `useLiveSession()` (refresh on a realtime nudge plus every 15 s), `useAnimatedNumber()` to glide values, `useSecondsLeft()` for the countdown, `BatteryRing.tsx`, `SessionSummary.tsx` once ended. `ActiveSessionProvider.tsx` (in `AppLayout`) polls `GET /api/me/sessions/active` for the app-bar pill and the Charging tab dot.
4. **Stop:** user: `POST /api/me/sessions/{id}/stop` → `stop_session()` → SQL `finish_session(..., 'USER_STOP', 'USER')`. Automatic: step 4 of section 8. `finish_session()` works out energy and bill, sets `bill_status` (`DUE` for app/instant sessions, `PAID` if the bill is 0), completes the booking and frees the charger.
5. **Outside sessions and faults:** `POST /api/admin/chargers/{id}/simulate` → `features/chargers/service.py` `simulate()` → SQL `simulate_charger_event()`: `EXTERNAL_START` (refused while the charger is reserved), `EXTERNAL_STOP`, `UNPLUG`, `FAULT`, `RECOVER`. A charger's status changes only through `apply_charger_event()`; every event, including refusals, is a row in `charger_events`.
6. **Paying the bill is not built** (the summary's Pay button is disabled; see `docs/PLAN.md`).

---

## 10. Live updates (realtime)

1. Triggers `bookings_notify`, `chargers_notify`, `charging_sessions_notify` (`database/migrations/013_realtime.sql`) call `notify_station_change()`, which calls `realtime.send({station_id, charger_id}, 'changed', 'station:<id>', false)`. On a database without Realtime it does nothing; an error in it never fails the write.
2. `lib/realtime.ts` `subscribeToStation()` shares one Supabase client (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) and one channel per station; it ignores the message body.
3. `lib/useRealtimeRefresh.ts` calls the page's `refresh` (coalescing bursts into one, plus when the tab becomes visible) and polls every 30 s while a channel is down (or at `alwaysPollMs`). `useRealtimeDown()` drives `ReconnectingBanner.tsx` in `AppLayout`.
4. Listeners: `StationPage` (detail and availability), `ExplorePage` (the 20 nearest stations on screen), `BookingsPage` (upcoming bookings' stations, plus `useNoticeToasts()`), `TicketPage`, `useLiveSession`, `ActiveSessionProvider`.

---

## 11. Building the database

`python -m database.pipeline` (`database/pipeline.py` `main()`), safe to re-run:
1. `apply_pending()` (`database/migrate.py`) applies `database/migrations/*.sql` in order, each in its own transaction, recording them in `schema_migrations`.
2. `migrate_users.run()` copies accounts from `LEGACY_DATABASE_URL` (skipped if unset).
3. `import_legacy_manual.run()`, `import_osm.run()`, `import_ocm.run()` load stations (`database/imports/`, cleaning in `normalize.py`, Gujarat boundary in `regions.py`).
4. `dedupe.run()` merges stations within about 50 m.
5. `synthetic.run()` fills missing chargers, power, prices and ratings (labelled through `data_source = 'synthetic'` / `estimated_fields`; profiles in `database/seeds/profiles.py`).
6. `demo_data.run()` creates demo accounts (`@chargespot.test`), a week of demo bookings and kiosk devices.

Tests build a fresh schema each run from the same migrations (`backend/tests/conftest.py`, `database/tests/conftest.py`) in `TEST_DATABASE_URL`, a throwaway local database.
