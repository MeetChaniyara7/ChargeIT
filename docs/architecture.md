# ChargeSpot: Architecture

> **ChargeSpot is "BookMyShow for EV charging".** Drivers find nearby charging stations, see which chargers are free, book a time slot, and start charging at the station with a one-time code. Drivers without a booking can still walk in and pay by QR at the station screen.

This document records **what we are building and why**. It is the reference for the team and the project jury. Every decision here was agreed during Phase 0 planning (October 2026).

---

## Contents

1. [The big picture](#1-the-big-picture)
2. [Technology choices](#2-technology-choices)
3. [Where we started (existing code)](#3-where-we-started-existing-code)
4. [Folder structure](#4-folder-structure)
5. [Data model](#5-data-model)
6. [Booking lifecycle](#6-booking-lifecycle)
7. [Charging flows](#7-charging-flows)
8. [Payments and refunds](#8-payments-and-refunds)
9. [The station kiosk](#9-the-station-kiosk)
10. [Background jobs](#10-background-jobs)
11. [Live updates (realtime)](#11-live-updates-realtime)
12. ["Best station" recommendations](#12-best-station-recommendations)
13. [Station data strategy](#13-station-data-strategy)
14. [Security](#14-security)
15. [Configuration values](#15-configuration-values)
16. [Free services and their limits](#16-free-services-and-their-limits)
17. [Build phases and team split](#17-build-phases-and-team-split)

---

## 1. The big picture

ChargeSpot has **two front-end apps and one API**. Every rule about availability, booking, payment and charging lives in the API and the database. **The front ends never decide availability themselves.** They ask the API.

```mermaid
flowchart LR
    subgraph Users
        U[Driver's phone / laptop]
        K[Station kiosk tablet]
        A[Admin]
    end

    subgraph Frontends["Front ends (Vercel)"]
        W[User web app<br/>React + Vite]
        KA[Station kiosk app<br/>React + Vite]
    end

    subgraph Backend["API (Render)"]
        API[FastAPI<br/>routers → services → repositories]
    end

    subgraph Supabase["Supabase (free tier)"]
        DB[(PostgreSQL<br/>+ btree_gist + pg_cron)]
        RT[Realtime]
    end

    subgraph External["Free external services"]
        G[Google Sign-In]
        RZ[Razorpay<br/>TEST MODE]
        OSRM[OSRM routing]
        NOM[Nominatim geocoding]
        TILES[OpenStreetMap tiles]
    end

    U --> W
    A --> W
    K --> KA
    W -->|HTTPS + JWT| API
    KA -->|HTTPS + device key| API
    API --> DB
    DB -->|"change nudges"| RT
    RT --> W
    RT --> KA
    API --> G
    API --> RZ
    RZ -->|webhook| API
    API --> OSRM
    API --> NOM
    W --> TILES
```

| Part | Who uses it | What it does |
|---|---|---|
| **User web app** | Drivers, admins | Search the map, see live availability, get "best station" suggestions, book and pay, receive the OTP, watch charging progress, pay the energy bill, manage bookings. Admins edit stations and chargers. |
| **Station kiosk app** | Anyone at the station | One shared screen per station. Shows every charger's status and progress. Starts charging, either with a booking OTP or by walk-in QR payment. |
| **API** | Both apps | All business logic: availability, bookings, payments, OTPs, charging sessions, scheduling, recommendations. |
| **Database** | API only | Stores everything, and **enforces the most important rule (no double booking) itself**. |

---

## 2. Technology choices

Everything is **free**. No paid service is used.

| Need | Choice | Why |
|---|---|---|
| User web app | React 19, Vite, TypeScript, Tailwind CSS (already built) | Existing, working app; we extend it rather than rewrite it. |
| Kiosk app | Same stack as the web app | The team already knows it. The two apps share types and constants. |
| API | **FastAPI (Python)**, kept from the existing project | Working Google sign-in is already built on it, and the jury has seen it. Python suits the data-import and scoring scripts. FastAPI generates live API docs at `/docs`, and pytest makes the concurrency test simple. |
| Database | PostgreSQL on **Supabase** | The `btree_gist` extension makes "no double booking" a database rule. `pg_cron` runs jobs every minute. Realtime pushes live updates. |
| Migrations | Numbered plain `.sql` files plus a small Python runner | Easy for a reader to follow; the booking constraint has to be written in raw SQL anyway. Replaces the old `create_all()` call, which could never change existing tables. |
| Background jobs | **pg_cron** (inside the database) | Render's free tier puts the API to sleep after about 15 idle minutes, so a timer inside the API would stop firing. pg_cron runs inside Supabase around the clock. |
| Payments | **Razorpay test mode** | Free; supports UPI, cards and netbanking. The API verifies every payment with Razorpay's signature, never by trusting the browser. |
| Maps | Leaflet with **OpenStreetMap** tiles | Free with attribution and no key. A CSS filter darkens them to match the UI. (CARTO basemaps now require an API key, so we don't use them.) |
| Routing / travel time | OSRM public server, falling back to straight-line distance | Free. One request per recommendation. |
| Address search | Nominatim (OpenStreetMap), called through the API with a cache | Free. Its usage policy forbids search-as-you-type, so we geocode only when the user presses Search. |
| Shared front-end types | TypeScript types generated from the API's OpenAPI spec (`openapi-typescript`) | The two apps always match the API without hand-copying types. |
| Kiosk QR codes | `qrcode.react` | Tiny, MIT-licensed. Draws the walk-in payment QR. |
| Hosting | Vercel (both front ends), Render (API) | Free tiers. |

**Time zones:** all times are stored in **UTC** (`timestamptz`) and displayed in **Asia/Kolkata (IST)**.

---

## 3. Where we started (existing code)

Phase 0 began with an audit of the existing code. Summary:

| Area | State | What we do with it |
|---|---|---|
| Google sign-in, email login, JWT (`backend/auth`, `routes/auth.py`, `AuthContext`) | Works. The Google ID token is already verified on the server. | **Keep.** Move into the new structure; fix the fixed OAuth `state` value and move hard-coded secrets and URLs into `.env`. |
| Routing (`App.tsx`, `ProtectedRoute`) | Works | **Keep.** |
| Map and station list (`Dashboard`, `StationMap`, `StationCard`) | Works, but one 361-line page does everything, fetches every station at once, defaults to San Francisco, shows `$` prices, and **invents values when data is missing** | Split into smaller files and hooks. Query by map area. Default to Ahmedabad. Use ₹. Show "unknown" or an "approximate data" badge instead of made-up numbers. |
| Domain API (`main.py`) | All routes in one file; most are **unauthenticated** (for example, anyone can list every user's email) | Rebuild as feature modules, each with proper authentication. |
| Database schema | Created by `create_all()`, hand-edited in DBeaver, no migrations, no overlap protection on reservations | Replace with numbered migrations (see section 5). |
| Station import script | Broken (writes columns that don't exist; falls back to San Francisco data) | Replace with new import scripts (see section 13). |
| Leftovers | Supabase-auth client, unused `Header.tsx` and `App.css`, committed `.vite/` folder, outdated README, "AI agent – coming soon" button | Remove. The Supabase client is reused only for Realtime. |
| Tests | None | Add (see section 17). |

---

## 4. Folder structure

One repository with **four top-level areas**, named for what they are, so a new teammate or the jury can find anything quickly:

| Folder | What it holds | Language |
|---|---|---|
| `backend/` | The API: every business rule | Python (FastAPI) |
| `frontend/` | Everything that runs in a browser: the driver web app, the station kiosk, and the code they share | TypeScript (React) |
| `database/` | The schema (migrations), demo data (seeds), station import scripts, and saved SQL queries | SQL + Python |
| `docs/` | Architecture, build plan, setup guide | Markdown |

The two front ends and their shared package form an **npm workspaces** monorepo (one `npm install` at the root). The backend is a separate Python project with its own virtual environment.

```
backend/
  app/main.py                    app setup, middleware, routers
  app/config.py                  every setting and business rule in one place
  app/db.py                      database connection
  app/core/                      error format, logging
  app/features/
    auth/                        Google + email login, JWT, require_admin
    stations/                    station search by map area or radius
    availability/                30-minute slot grid per charger
    recommendations/             scoring.py (pure functions), osrm.py
    bookings/                    state_machine.py, otp.py, refunds.py, service.py, repository.py
    payments/                    Razorpay orders, signature check, webhook, refunds
    charging/                    sessions, simulated energy meter, billing
    kiosk/                       device auth, OTP start, walk-in start, rate limits
    chargers/                    charger simulator (fake OCPP events)
    geocoding/                   Nominatim proxy + cache
    vehicles/                    the user's vehicles
    admin/                       station/charger editing, reports, alerts
  scripts/                       admin helpers, e.g. make_admin.py
  tests/
frontend/
  user-web/                      the driver web app (also hosts the admin pages)
    src/app/                       App.tsx, routes
    src/components/layout/         Navbar and other page chrome
    src/features/auth/             AuthContext, login/register, ProtectedRoute
    src/features/home/             landing page
    src/features/stations/         map, list, search, station page
    src/features/bookings/         slot grid, checkout, confirmation, My Bookings
    src/features/charging/         live session page, energy bill payment
    src/features/admin/            station/charger editor, reports
    src/lib/                       api client, realtime
  kiosk/                         the station screen (from Phase 6)
    src/features/device/           one-time device setup (API key)
    src/features/status-board/     charger tiles: availability + progress
    src/features/otp-start/        "Start with OTP"
    src/features/walk-in/          "Take a charger" + payment QR
  shared/                        @chargespot/shared: constants (statuses, connector
                                 types), ₹ and IST formatting, generated API types
database/
  migrate.py                     applies migrations in order
  migrations/                    001_extensions.sql, 002_users_vehicles.sql, …
  seeds/                         synthetic chargers, demo users, bookings and kiosk devices
  imports/                       OSM + Open Charge Map import, normalise, dedupe
  queries/                       saved read-only SQL for DBeaver: reports, checks, demo
docs/                            architecture.md (this file), phases.md, setup.md, …
data/                            raw downloads and legacy CSVs (git-ignored, never committed)
```

**Inside each backend feature**, files follow the same pattern: **router** (HTTP), **service** (rules), **repository** (SQL), **schemas** (validation), **models** (tables). Front-end features keep their pages, components and hooks together in one folder.

---

## 5. Data model

### 5.1 Overview

```mermaid
erDiagram
    users ||--o{ vehicles : owns
    users ||--o{ bookings : makes
    operators ||--o{ stations : runs
    stations ||--o{ chargers : has
    stations ||--o{ station_devices : "has kiosk"
    chargers ||--o{ bookings : "is booked in"
    chargers ||--o{ charger_events : reports
    bookings ||--o{ booking_events : "history"
    bookings ||--o| charging_sessions : "becomes"
    chargers ||--o{ charging_sessions : runs
    bookings ||--o{ payments : "paid by"
    station_devices ||--o{ otp_attempts : logs

    users {
        uuid user_id PK
        text email UK
        text google_user_id UK
        text role "USER | ADMIN"
    }
    stations {
        uuid station_id PK
        text name
        float lat
        float lng
        text data_source "ocm|osm|synthetic|manual"
    }
    chargers {
        uuid charger_id PK
        uuid station_id FK
        text connector_type
        numeric power_kw
        numeric price_per_kwh
        text status
        text data_source
    }
    bookings {
        uuid booking_id PK
        uuid user_id FK "null for walk-ins"
        uuid charger_id FK
        tstzrange time_range
        text source "APP|INSTANT|WALK_IN"
        text status
        text otp_hash
    }
    charging_sessions {
        uuid session_id PK
        uuid booking_id FK "null for EXTERNAL"
        uuid charger_id FK
        text source "BOOKING|WALK_IN|EXTERNAL"
        numeric energy_kwh
        numeric bill_amount
        text bill_status
    }
    payments {
        uuid payment_id PK
        uuid booking_id FK
        text purpose
        text status
        numeric amount
        numeric refunded_amount
    }
```

**Naming:** primary keys are `<table>_id` (UUID), matching the existing code so the auth module needs almost no changes. Fixed lists such as statuses are `text` columns with a `CHECK` constraint, which is easier to change later than PostgreSQL enums.

### 5.2 Tables

| Table | Key columns | Notes |
|---|---|---|
| `users` | email (unique, lower-case), full_name, phone, google_user_id (unique), password_hash (optional), role `USER`/`ADMIN` | From Google sign-in or email registration. |
| `vehicles` | user_id, nickname, connector_type, battery_kwh | One default vehicle per user (partial unique index). |
| `operators` | name (normalised, unique), website | "Tata Power", "Jio-bp", … Duplicate spellings are merged on import. |
| `stations` | name, address, city, state, postcode, lat, lng, operator_id, amenities, opening hours, rating, is_active, **data_source**, external_ref | `external_ref` is e.g. `osm:node/123` or `ocm:4567`; `(data_source, external_ref)` is unique so imports can be re-run safely. Indexed on (lat, lng). |
| `chargers` | station_id, label (e.g. "CCS2-1"), connector_type, current_type `AC`/`DC`, power_kw, price_per_kwh, **status**, **data_source** | **One row = one bookable plug.** `data_source` is per charger because an imported station can have synthetic chargers. |
| `bookings` | user_id, charger_id, vehicle_id, **time_range**, **source**, **status**, hold_expires_at, otp_hash, otp_used_at, booking_fee, refund_amount, cancelled_at | See 5.3 for the constraints. |
| `booking_events` | booking_id, from_status, to_status, actor `USER`/`DEVICE`/`SYSTEM`/`ADMIN`, reason, at | Written automatically by a trigger. A full audit trail of every status change. |
| `charging_sessions` | booking_id, charger_id, device_id, **source**, started_at, ended_at, end_reason, energy_kwh, **bill_amount**, **bill_status**, prepaid_amount, paid_at | Live energy and % are **calculated** from elapsed time × charger power, not stored every second. |
| `payments` | booking_id, **purpose** `BOOKING_FEE`/`ENERGY`/`WALKIN_PREPAID`, provider `razorpay`, provider_order_id (unique), provider_payment_id (unique), amount, status, refunded_amount | Each refund is recorded against its payment. |
| `webhook_events` | provider_event_id (primary key), payload, received_at, processed_at | Razorpay may send the same webhook twice; we process each event once. |
| `station_devices` | station_id, name, api_key_hash, key_prefix, is_active, last_seen_at | One kiosk per station. The key is stored only as a hash. |
| `otp_attempts` | device_id, attempted_at, success | Used for the kiosk's wrong-OTP cooldown. |
| `charger_events` | charger_id, event (`AVAILABLE`, `CHARGING`, `FINISHED`, `FAULTED`, …), source, at | Simulated OCPP messages (see 7.4). |
| `geocode_cache` | normalised query, result, fetched_at | Avoids repeating Nominatim calls. |

**Lists used in CHECK constraints** (mirrored in `frontend/shared`):

- **Connector types:** `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001` (displayed as "Bharat DC-001 (GB/T)"), `TYPE1`, `OTHER`
- **Charger status** (the live physical state, reported by the charger): `AVAILABLE`, `RESERVED`, `CHARGING`, `FAULTED`, `OUT_OF_SERVICE`
- **Booking source:** `APP` (booked ahead, ₹199 fee), `INSTANT` ("Charge now" in the web app, no fee), `WALK_IN` (kiosk QR, no account)
- **Booking status:** `HELD`, `CONFIRMED`, `ACTIVE`, `COMPLETED`, `EXPIRED`, `CANCELLED`, `NO_SHOW`
- **Session source:** `BOOKING`, `WALK_IN`, `EXTERNAL` (someone used the operator's own app or card)
- **Bill status:** `DUE`, `PAID`, `PREPAID_SETTLED`

### 5.3 The rule that prevents double booking

The most important rule in the project is enforced **by PostgreSQL itself**, not by application code. Two people pressing "Book" at the same instant cannot both succeed:

```sql
-- One charger can never have two live bookings whose time ranges overlap.
ALTER TABLE bookings ADD CONSTRAINT no_double_booking
  EXCLUDE USING gist (
    charger_id WITH =,      -- same charger
    time_range WITH &&      -- overlapping time
  )
  WHERE (status IN ('HELD', 'CONFIRMED', 'ACTIVE'));
```

Why this matters: an application-level check ("is the slot free? then insert") has a gap between the check and the insert, so two requests can both pass the check. The database constraint has no gap. When it rejects a booking (error code `23P01`), the API replies **"This slot was just taken"** together with alternative times and chargers.

The constraint covers **every** way a charger gets used: app bookings, instant bookings and kiosk walk-ins are all rows in `bookings`. A walk-in can therefore never overlap an app booking.

Other database rules:

- `time_range` must have its start before its end, using `[start, end)` bounds.
- **One hold per user at a time** (`UNIQUE (user_id) WHERE status = 'HELD'`), so nobody can hoard slots.
- `user_id` is required unless `source = 'WALK_IN'`.
- A trigger rejects **illegal status changes** (see section 6), even when they come from a background job.
- **Row-level security is switched on for every table with no policies.** Supabase exposes tables through its public REST API, and this blocks that route completely. Only our API, using the database connection string, can read or write data.

---

## 6. Booking lifecycle

### 6.1 States

```mermaid
stateDiagram-v2
    [*] --> HELD: user picks a slot (APP)
    [*] --> CONFIRMED: "Charge now" (INSTANT, no fee)
    [*] --> HELD: kiosk walk-in, QR shown (WALK_IN)

    HELD --> CONFIRMED: ₹199 payment verified → OTP issued
    HELD --> ACTIVE: walk-in QR payment verified → charging starts
    HELD --> EXPIRED: hold time passed without payment
    HELD --> CANCELLED: user backs out of payment

    CONFIRMED --> ACTIVE: correct OTP entered at kiosk
    CONFIRMED --> NO_SHOW: no OTP by start + 10 min
    CONFIRMED --> CANCELLED: user cancels (refund by rules)<br/>or charger occupied/faulty (full refund)

    ACTIVE --> COMPLETED: stopped, auto-stopped at slot end,<br/>or prepaid amount used up

    EXPIRED --> [*]
    NO_SHOW --> [*]
    CANCELLED --> [*]
    COMPLETED --> [*]
```

All transitions live in **one module** (`bookings/state_machine.py`). A database trigger enforces the same table of allowed transitions, so neither the API nor a background job can make an illegal change.

### 6.2 Rules

| Rule | Value |
|---|---|
| Slot size | **30-minute blocks**; a booking is **1–4 blocks** |
| Payment hold | A new `APP` booking is `HELD` for **5 minutes**. Razorpay Checkout is given a slightly shorter timeout so it closes first. |
| Booking fee | **₹199** for `APP` bookings. **No fee** for `INSTANT` and `WALK_IN`. |
| OTP | **6 digits**. Valid from **start − 15 min to start + 10 min**. **Single use to start charging.** |
| Reservation lock | At **start − 15 min** the charger is told to reserve itself for this booking (see 7.4). |
| No-show | No OTP by **start + 10 min** → `NO_SHOW`. **The ₹199 fee is kept.** The charger is free for the rest of the window. |
| End of slot | Charging **stops automatically at slot end**, with a warning **5 minutes before**. |
| Unpaid bills | A user with an unpaid energy bill **cannot make a new booking** until it is paid. |

**Lazy checks:** stale holds and missed OTPs are resolved **when anyone looks at a charger**, not only when the job runs. Before creating a booking, the API expires old holds on that charger in the same transaction. Correctness therefore never depends on when the background job last ran.

### 6.3 Cancellation refunds (of the ₹199 fee)

| Cancelled | Refund |
|---|---|
| **2 hours or more** before start | **100%** (₹199) |
| **30 minutes to 2 hours** before | **75%** (₹149.25) |
| **15 to 30 minutes** before | **50%** (₹99.50) |
| **Less than 15 minutes** before | **0%** |
| No-show | **0%** (fee kept) |
| Charger occupied or faulty at start, with no alternative charger | **100%**, not the user's fault |

In test mode, refunds are calculated and **recorded**, not sent as real money.

---

## 7. Charging flows

### 7.1 App booking (booked ahead)

```mermaid
sequenceDiagram
    actor D as Driver (web app)
    participant API
    participant DB as Database
    participant RZ as Razorpay (test)
    participant K as Station kiosk
    participant C as Charger (simulated)

    D->>API: Book charger ③, 10:00–11:00
    API->>DB: INSERT booking (HELD, expires in 5 min)
    alt slot already taken
        DB-->>API: exclusion violation (23P01)
        API-->>D: "Slot just taken" + alternatives
    end
    API->>RZ: create ₹199 order
    D->>RZ: pay (UPI / card / netbanking)
    D->>API: payment result + signature
    API->>API: verify signature
    API->>DB: HELD → CONFIRMED, store OTP hash
    API-->>D: OTP 482913 (shown once; can be regenerated)

    Note over API,C: 09:45: reservation lock sent to charger ③

    D->>K: enters OTP 482913
    K->>API: start (device key + OTP)
    API->>DB: CONFIRMED → ACTIVE, create session
    API->>C: start charging
    K-->>D: "Go to Charger ③, plug in"

    Note over D,API: Driver watches progress on their phone

    API->>C: stop at 11:00 (warning at 10:55)
    API->>DB: ACTIVE → COMPLETED, bill = kWh × price
    API-->>D: "Charging complete – pay ₹223.20"
    D->>RZ: pay energy bill in the web app
    API->>DB: bill PAID
```

### 7.2 Instant booking ("Charge now" in the web app)

For a signed-in user who is already at, or near, a free charger:

1. On the station page, tap **Charge now** on a free charger. This books the time from now until the earlier of that charger's next booking (minus 5 minutes) or 2 hours.
2. **No ₹199 fee.** The booking goes straight to `CONFIRMED` and the OTP appears immediately.
3. From here it is identical to 7.1: OTP at the kiosk, live progress on the phone, energy bill paid in the web app.

### 7.3 Kiosk walk-in (no app, no account)

```mermaid
sequenceDiagram
    actor W as Walk-in driver
    participant K as Station kiosk
    participant API
    participant RZ as Razorpay (test)
    participant C as Charger (simulated)

    W->>K: Take a charger → ③ (free until 12:30, ₹18/kWh)
    W->>K: choose ₹200
    K->>API: create walk-in (charger ③, ₹200)
    API->>API: create WALK_IN booking (HELD) for now → 12:25<br/>(protected by the same no-overlap rule)
    API->>RZ: create payment link for ₹200
    API-->>K: payment link
    K-->>W: shows QR code
    W->>RZ: scans QR, pays with any UPI app
    RZ-->>API: payment confirmed (webhook)
    API->>C: start charging
    K-->>W: "Payment received ✓ – plug in at Charger ③"
    Note over C: Stops when ₹200 is used up,<br/>when the driver stops it at the charger,<br/>or 5 min before the next booking
    API->>API: settle: used ₹186, refund ₹14 (recorded)
    K-->>W: tile ③ shows "Done · used ₹186 · ₹14 refunded"
```

- **Pay first, then charge.** Razorpay confirms the payment before the charger starts, so nobody can leave without paying, and no staff are needed.
- **No phone number or SMS.** The walk-in is identified only by their payment. Sending SMS codes would cost money.
- ChargeSpot collects the money and **records the operator's share** for later payout, the same way aggregator apps work.
- While the QR is on screen, the walk-in booking is `HELD` (just like an app booking waiting for payment). If payment isn't completed within **3 minutes**, it becomes `EXPIRED` and the charger is freed.

### 7.4 Chargers used outside ChargeSpot

Stations belong to real operators, and drivers can also start a charger with the operator's own app or card. Real chargers report their status to the operator using a standard protocol called **OCPP**. OCPP can also **reserve** a charger so that only one customer can start it.

We cannot connect to real chargers, so the API includes a **charger simulator** that produces the same kinds of events. The admin page has a **"Simulate external session"** button for demos.

| Situation | What happens |
|---|---|
| No booking right now | Anyone may use the charger. An outside session appears as **"Busy"**, and that time block isn't offered to app users. |
| 15 minutes before a booking | The charger is **reserved** and rejects outside starts. |
| An outside session is still running when the lock time comes | The booked driver is warned that the charger may be busy. The system checks again at the start time. |
| Still occupied at the start time | ① **Move the booking to another free compatible charger** at the same station and tell the driver. ② If none is free, **cancel with a 100% refund** and show nearby alternatives. The driver is never penalised. |

---

## 8. Payments and refunds

| What | Who pays | How | Verified by |
|---|---|---|---|
| **Booking fee ₹199** (APP bookings) | Signed-in user | Razorpay Checkout in the web app | Razorpay signature, checked by the API |
| **Energy bill** (APP and INSTANT bookings) | Signed-in user | Razorpay Checkout in the web app, after charging | Razorpay signature; webhook as a backup |
| **Walk-in prepayment** | Anyone at the kiosk | QR code on the kiosk → Razorpay payment link | Razorpay webhook, **before** charging starts |
| Refunds | — | Calculated by the API and recorded (test mode) | — |

**Rules that apply to every payment:**

- **Amounts are calculated only on the server.** Front ends display them; they never send them.
- A payment is marked paid **only** after the API has verified it with Razorpay.
- Each Razorpay webhook event is processed once (`webhook_events` table).
- A bill that is already paid cannot be charged again.
- The kiosk **never shows bills or personal details** for app users. Those live in the web app behind login.

**Energy bill** = energy delivered (kWh) × charger's price per kWh, rounded to 2 decimals. In the simulation, energy = charger power × charging time × an efficiency factor, limited by the vehicle's battery size.

---

## 9. The station kiosk

**One kiosk per station, shared by everyone**, like an ATM. Each person uses it for under a minute. Everything personal happens on their own phone.

```
┌──────────────────────────────────────────────────────────┐
│  ChargeSpot · Tata Power – Gota                 10:42 AM │
├──────────────────────────────────────────────────────────┤
│ ① CCS2 60kW   CHARGING   ███████░░ 72%   ends 11:00      │
│ ② CCS2 60kW   RESERVED   for 11:00 booking               │
│ ③ Type2 22kW  AVAILABLE  free until 12:30 · ₹18/kWh      │
│ ④ CCS2 30kW   CHARGING   walk-in · ₹120 of ₹200 used     │
├──────────────────────────────────────────────────────────┤
│ [ Start with OTP ]   booked in the ChargeSpot app        │
│ [ Take a charger ]   no booking? pay by UPI QR here      │
└──────────────────────────────────────────────────────────┘
```

| Feature | Design |
|---|---|
| **Status board** | Every charger's state, progress and "free until" time, updated live. **No names, phone numbers or bills.** |
| **Start with OTP** | For app and instant bookings. The OTP matches exactly one booking at this station, which tells the kiosk which charger to start. |
| **Take a charger** | Walk-in flow (section 7.3). The price and payment method are shown before anyone starts. |
| **Stopping and paying** | Not on the kiosk. App users use the web app. Walk-ins stop at the charger, or charging auto-stops. |
| **Auto-reset** | After **30 seconds** without a touch, the kiosk returns to the status board. |
| **Wrong OTPs** | After **5 wrong tries**, a **2-minute cooldown**. A hard lockout would let one person block everyone. **20+ wrong tries in 10 minutes** raises an alert on the admin page. |
| **Device login** | The kiosk signs in as a **station device** with a per-station API key, entered once during setup and stored only as a hash on the server. It can act only on its own station. |

---

## 10. Background jobs

Jobs run **every minute** using **pg_cron** inside the database. Each job is a SQL function, so tests can call it directly.

| Job | What it does |
|---|---|
| `expire_holds()` | `HELD` bookings past their hold time (5 min for app bookings, 3 min for walk-in QR) → `EXPIRED` |
| `apply_reservation_locks()` | Reserve chargers whose booking starts in ≤ 15 minutes |
| `resolve_occupied_starts()` | Booking start time reached but the charger is busy → move to another charger, or cancel with a full refund |
| `mark_no_shows()` | No OTP by start + 10 min → `NO_SHOW`, fee kept |
| `auto_stop_sessions()` | Stop sessions at slot end, when a walk-in's prepaid amount is used up, or 5 minutes before the next booking. Calculate the bill. |

Every job function takes the current time as an optional parameter (`p_now timestamptz DEFAULT now()`), so tests can simulate any moment without waiting.

**Why pg_cron instead of a scheduler inside the API?** The free Render server sleeps when idle, so an in-app timer would silently stop. pg_cron keeps running inside Supabase. The lazy checks in section 6.2 add a second layer of safety.

---

## 11. Live updates (realtime)

When a booking or charger changes, a database trigger sends a small **"something changed"** message through Supabase Realtime, for example `{ station_id, charger_id }`. The web app and kiosk then **re-fetch fresh data from the API**.

- The message carries no booking details, so nothing private leaks through Realtime.
- The API stays the **single source of truth**. Realtime is only a nudge to refresh.

---

## 12. "Best station" recommendations

`GET /recommendations?lat&lng&connector&start&duration`

1. Find stations within **15 km** that have chargers matching the connector type.
2. Take the nearest candidates by straight-line distance and ask **OSRM** for driving times **in one request**. If OSRM fails, estimate time from straight-line distance at 25 km/h.
3. Score each station with a **weighted formula**. The weights are a config object, so they're easy to tune and explain:

| Factor | Better when… |
|---|---|
| Travel time | shorter |
| Compatible chargers free for the requested time | more |
| Charging power (kW) | higher |
| Price per kWh | lower |
| Rating | higher |
| Data quality | real data scores slightly higher than synthetic |

4. Return the top results with a short **reason**, for example *"2 CCS2 chargers free · 1.2 km · 60 kW"*.

The scoring code is **pure functions** with no database or network access, so it has its own unit tests.

---

## 13. Station data strategy

Real Indian charging data is incomplete, especially prices and connector details. Our approach:

1. **Keep the 10 hand-verified Ahmedabad stations** from the old database (`VERIFY-ST-001` to `010`, operators such as Tata Power, IOCL, CESL and Jio-bp) as `data_source = manual`.
2. **Import Gujarat first** from OpenStreetMap (Overpass API, `amenity=charging_station`) and Open Charge Map (free API key). Other states can be added later by changing one setting.
3. **Clean the data:**
   - **Remove duplicates:** stations within **~50 m** with similar names are merged.
   - **Merge operator spellings,** e.g. `tata`, `TATA`, `Tata power`, `Tata Power EZ Charge` → **Tata Power**.
   - **Standardise connector names** to our list (GB/T → Bharat DC-001, and so on).
   - **Drop things that aren't car chargers:** battery-swap points (Honda e:swap, Battery Smart, Sun Mobility), bike stations (Yulu), phone-charging points.
4. **Fill gaps with synthetic data,** clearly labelled. Stations with no charger details get realistic chargers, power and prices based on the operator and location, tagged `data_source = synthetic`. Ahmedabad also gets demo bookings so the slot grid looks realistic.
5. **Be honest in the UI.** Synthetic chargers show a small **"approximate data"** badge. Unknown values show "unknown" and are never invented.
6. **Admin page** to add or correct stations and chargers by hand (`data_source = manual`).

**Licences:** OpenStreetMap data is ODbL and Open Charge Map is CC BY 4.0. Both require attribution, shown in the app footer and the README.

The old exported CSVs live in `/data/legacy/` and are **git-ignored**. The exported `users` table is **not** imported; users simply sign in with Google again.

---

## 14. Security

| Area | Measure |
|---|---|
| Secrets | Only in `.env` files, never committed. Each app has a `.env.example`. **The database password that was committed in the old `database.py` must be changed** and removed from the code. |
| User sign-in | Google ID token verified on the server; the API issues its own JWT. The OAuth redirect flow gets a random `state` value. |
| Authorisation | Every user route requires login, and users can only see their own bookings, sessions and bills. Admin routes require `role = ADMIN`. |
| Kiosk | Per-station API key, stored as a hash; it can act only on its own station. |
| OTP | Stored as an **HMAC-SHA256** with a server secret, because a plain hash of a 6-digit code can be cracked in seconds. Unique among live bookings at the same station. Valid only in its time window. Wrong-attempt cooldown on the kiosk. |
| Database | Row-level security on every table blocks Supabase's public REST API. Only the API connects. |
| Payments | Server-calculated amounts, Razorpay signature checks, one-time webhook processing. |
| CORS | Allowed origins come from config, not hard-coded localhost. |

---

## 15. Configuration values

All of these live in `backend/app/config.py`, so they can be changed without touching business logic.

| Setting | Value |
|---|---|
| Slot length | 30 min |
| Blocks per booking | 1–4 |
| Payment hold (app booking) | 5 min |
| Walk-in QR hold | 3 min |
| How far ahead users can book | 7 days |
| Booking fee (APP) | ₹199 |
| OTP valid from / until | start − 15 min / start + 10 min |
| Reservation lock | start − 15 min |
| No-show after | start + 10 min |
| End-of-slot warning | 5 min before |
| Walk-in / instant buffer before next booking | 5 min |
| Instant booking maximum | 2 h |
| Walk-in amounts | ₹100, ₹200, ₹500, or "until the next booking" |
| Refund tiers | ≥ 2 h: 100% · 30 min–2 h: 75% · 15–30 min: 50% · < 15 min: 0% |
| Kiosk wrong-OTP cooldown | 5 tries → 2 min |
| Kiosk alert threshold | 20 wrong tries / 10 min |
| Kiosk idle reset | 30 s |
| Recommendation radius | 15 km |
| Duplicate-station distance | ~50 m |
| Display time zone | Asia/Kolkata |

---

## 16. Free services and their limits

| Service | Limit or risk | How we handle it |
|---|---|---|
| Supabase free tier | Pauses after 7 days without activity. Direct database connections are IPv6-only. | Open the project regularly. The API uses Supabase's **session pooler** connection string, which Render can reach. |
| Render free tier | Sleeps after ~15 idle minutes; ~30 s cold start | Background jobs run in pg_cron instead. Open the app a minute before a demo. |
| Razorpay test mode | No real money moves | Exactly what we want. Refunds are recorded, not sent. |
| Razorpay webhooks | Need a public URL | Works on Render. Locally, a free tunnel (e.g. cloudflared) or rely on the signature check alone. |
| OSRM public server | Light use only; no uptime guarantee | One request per recommendation, plus the straight-line fallback. |
| OpenStreetMap tile server | Fair use only (light traffic, attribution shown, no bulk downloading) | Fine for a college project and demo. For real production traffic, switch to a free-tier tile provider with a key. |
| Nominatim | Max 1 request/s; no search-as-you-type | Search only on submit, through the API, with a cache. |
| Overpass / Open Charge Map | Rate limits | Imports are run occasionally by a script, not by users. |

---

## 17. Build phases and team split

Each phase ends with a review. The next phase starts only after approval.

| Phase | Scope | Effort |
|---|---|---|
| **0** | Audit, decisions, this document | done |
| **1** | Monorepo restructure; split the API into feature modules; lock down routes; fix secrets and OAuth `state`; shared package and generated types; rename to ChargeSpot | 3–4 person-days |
| **2** | Database migrations (constraints, triggers, RLS, job functions); OSM and OCM import for Gujarat; dedupe and normalisation; synthetic seed | 5–6 person-days |
| **3** | Station search by area; availability grid; recommendations with tests; geocoding proxy; map and list UI fixes | 5–6 person-days |
| **4** | Slot picker (BookMyShow-style); hold and payment; OTP confirmation; My Bookings; cancellation with refunds; instant bookings | 7–8 person-days |
| **5** | pg_cron jobs; lazy checks; realtime updates; charger simulator and reservation locks | 4–5 person-days |
| **6** | Kiosk app: device setup, status board, OTP start, walk-in QR flow; energy billing and payment in the web app | 6–7 person-days |
| **7** | Admin page; edge cases; full test suite; README; jury demo script; deployment | 6–8 person-days |

**Suggested team split (4 people):**

| Person | Focus |
|---|---|
| A, backend core | Bookings, state machine, OTP, payments, jobs, concurrency tests |
| B, data and database | Migrations, imports, cleaning, synthetic seed, recommendation scoring, admin API |
| C, user web app | Map and search, slot grid, checkout, My Bookings, live session page, realtime |
| D, kiosk and delivery | Kiosk app, charger simulator UI, admin page, docs and diagrams, deployment, demo script |

With **3 people**, D's work is shared between B (kiosk API, admin) and C (kiosk UI).

**Tests we will write:**

- **Concurrency:** two simultaneous bookings for the same slot → exactly one succeeds.
- **State machine:** every allowed transition works; every illegal one is rejected, by both the API and the database.
- **OTP:** correct code, wrong code, outside the time window, reused code, cooldown.
- **Jobs:** hold expiry, no-show at +10 min, auto-stop, occupied-charger handling.
- **Refunds:** each cancellation tier boundary.
- **Recommendation scoring:** weights, ordering, and the "why" text.
- **Walk-ins:** a walk-in can't overlap a booking; unpaid walk-ins are released; leftover amounts are refunded correctly.
