# API reference

Generated from the running app's own OpenAPI spec (`app.openapi()`, the same data as `http://localhost:8000/docs`) plus the `AppError` codes found in `backend/app/`. If an endpoint is missing here, the code has changed since this file was written: regenerate it from `/docs` or `/openapi.json`.

## Conventions

- **Base URL:** `http://localhost:8000` locally. Almost everything is under `/api`; the authentication routes also exist without it as `/auth/...`.
- **Auth:** `Authorization: Bearer <JWT>`. The JWT is issued by `POST /auth/login`, `POST /auth/register` or `POST /auth/google` and lasts `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 1440). Missing or bad token: `401`. Wrong role on `/api/admin/*`: `403`.
- **Errors:** every error is `{"error": {"code": "SLOT_TAKEN", "message": "...", "details": {...}}}`. `details` is present only for some codes (see below). Request-validation problems are `422` with code `VALIDATION_ERROR`. Code: `backend/app/core/errors.py`.
- **Times** are ISO 8601 in UTC (`2026-10-12T10:00:00Z`); the web app shows them in Asia/Kolkata. **Money** is a JSON number in rupees (`199.0`). A booking slot is `[start, end)`.
- **Health check:** `GET /health` is public and returns `{status, service, version}`.

## Endpoint index

| Method | Path | Auth | What it does |
|---|---|---|---|
| GET | `/health` | Public | Health |
| POST | `/auth/google` | Public | Google Id Token Login |
| GET | `/auth/google/callback` | Public | Google Callback |
| GET | `/auth/google/login` | Public | Google Login Redirect |
| POST | `/auth/login` | Public | Login |
| GET | `/auth/me` | Login required | Get Me |
| POST | `/auth/register` | Public | Register |
| POST | `/api/auth/google` | Public | Google Id Token Login |
| GET | `/api/auth/google/callback` | Public | Google Callback |
| GET | `/api/auth/google/login` | Public | Google Login Redirect |
| GET | `/api/stations` | Public | Search Stations |
| POST | `/api/stations` | Admin only | Create Station |
| GET | `/api/stations/count` | Public | How many stations are on the map (shown on the landing page). |
| GET | `/api/stations/{station_id}` | Public | Get Station |
| GET | `/api/stations/{station_id}/availability` | Public | Get Availability |
| GET | `/api/search/suggest` | Login required | Suggest |
| GET | `/api/recommendations` | Login required | Get Recommendations |
| GET | `/api/geocode` | Login required | Geocode |
| GET | `/api/me/vehicles` | Login required | List Vehicles |
| POST | `/api/me/vehicles` | Login required | Add Vehicle |
| DELETE | `/api/me/vehicles/{vehicle_id}` | Login required | Delete Vehicle |
| PATCH | `/api/me/vehicles/{vehicle_id}` | Login required | Change Vehicle |
| POST | `/api/bookings` | Login required | Hold a slot for 5 minutes. Pay the fee in that time (POST /api/payments/orders) to confirm it. |
| POST | `/api/bookings/instant` | Login required | "Charge now" on a free charger: no fee, confirmed at once, the code is in this response (once). |
| GET | `/api/bookings/{booking_id}` | Login required | Get Booking |
| POST | `/api/bookings/{booking_id}/cancel` | Login required | Cancel Booking |
| GET | `/api/bookings/{booking_id}/cancel-preview` | Login required | What you would get back if you cancelled right now (nothing changes). |
| POST | `/api/bookings/{booking_id}/otp` | Login required | A new one-time code. The old one stops working. |
| GET | `/api/me/bookings` | Login required | My Bookings |
| GET | `/api/me/dues` | Login required | Unpaid energy bills. While there are any, new bookings are refused (UNPAID_BILL). |
| POST | `/api/payments/orders` | Login required | The ₹199 booking-fee order for a held booking (the same order again if you ask twice). |
| POST | `/api/payments/verify` | Login required | Check Razorpay's signature, confirm the booking and return the one-time code (once). |
| POST | `/api/payments/webhook` | Public | Called by Razorpay, not by the browser. The signature covers the raw body, so read it untouched. |
| GET | `/api/me/sessions/active` | Login required | The session that is charging right now, or null. Powers the Charging tab and the app-bar pill. |
| GET | `/api/me/sessions/{session_id}` | Login required | Live values: energy, battery level, cost so far, time left. Only the owner can see a session. |
| POST | `/api/me/sessions/{session_id}/pay` | Login required | The Razorpay order for this session's energy bill (the amount is the bill the server worked out). |
| POST | `/api/me/sessions/{session_id}/pay/verify` | Login required | Check Razorpay's signature, mark the bill paid and return the updated session. |
| GET | `/api/me/sessions/{session_id}/receipt` | Login required | The receipt for a finished session (DUE bills show as unpaid). |
| POST | `/api/me/sessions/{session_id}/stop` | Login required | Stop charging now. The bill is worked out up to this moment. |
| POST | `/api/admin/bookings/{booking_id}/start` | Admin only | Demo stand-in for the kiosk: start charging for a confirmed booking as if its code was typed. |
| POST | `/api/admin/chargers/{charger_id}/simulate` | Admin only | Make a charger behave like a real one: an outside start (refused while it is reserved), a stop, |
| POST | `/api/kiosk/otp-start` | Kiosk device key | Start the charger of the booking this code belongs to. 5 wrong tries in a row: 2 minutes' wait (429 OTP_COOLDOWN). |
| GET | `/api/kiosk/status` | Kiosk device key | The status board: every charger's state, progress and free-until time. No names, phone numbers or bills. |
| POST | `/api/kiosk/walk-ins` | Kiosk device key | Take a free charger without a booking: holds it for 3 minutes and returns the payment link to show as a QR. |
| GET | `/api/kiosk/walk-ins/{walk_in_id}` | Kiosk device key | Has the walk-in paid yet? Poll this while the QR is on screen. |
| POST | `/api/kiosk/walk-ins/{walk_in_id}/cancel` | Kiosk device key | Back out of the QR screen: the charger is free again at once. |
| POST | `/api/admin/devices/{device_id}/disable` | Admin only | Switch a kiosk off (a lost tablet). Its key stops working at once. |
| GET | `/api/admin/stations/{station_id}/devices` | Admin only | List Devices |
| POST | `/api/admin/stations/{station_id}/devices` | Admin only | Create a kiosk key for a station. The key is in this response only; copy it to the tablet now. |
| GET | `/api/admin/activity` | Admin only | What admins changed, newest first. |
| GET | `/api/admin/alerts` | Admin only | Alerts |
| POST | `/api/admin/alerts/{alert_id}/seen` | Admin only | Alert Seen |
| GET | `/api/admin/bookings` | Admin only | Bookings by slot start (India-time days), newest first. |
| GET | `/api/admin/bookings/{booking_id}/events` | Admin only | The booking history: every status change, who made it and why. |
| PATCH | `/api/admin/chargers/{charger_id}` | Admin only | Edit a charger. Entering a power or price makes the value real: it loses its Approximate tag. |
| GET | `/api/admin/chargers/{charger_id}/affected` | Admin only | What taking this charger out of service would break: the future bookings, and whether someone is charging. |
| GET | `/api/admin/chargers/{charger_id}/events` | Admin only | The newest charger events first (the simulator live log). |
| POST | `/api/admin/chargers/{charger_id}/out-of-service` | Admin only | Take a charger out of service. With future bookings it needs `cancel_bookings = true` (409 HAS_FUTURE_BOOKINGS otherwise); |
| POST | `/api/admin/chargers/{charger_id}/restore` | Admin only | Put an out-of-service charger back in use. |
| GET | `/api/admin/devices` | Admin only | Devices |
| PATCH | `/api/admin/devices/{device_id}` | Admin only | Rename Device |
| POST | `/api/admin/devices/{device_id}/rotate` | Admin only | A new key for the same tablet and station. The old key stops working at once; the new one is in this answer only. |
| GET | `/api/admin/operators` | Admin only | Operators |
| POST | `/api/admin/operators` | Admin only | Create Operator |
| DELETE | `/api/admin/operators/{operator_id}` | Admin only | Only an operator with no stations can be deleted (409 OPERATOR_IN_USE otherwise). |
| PATCH | `/api/admin/operators/{operator_id}` | Admin only | Update Operator |
| GET | `/api/admin/overview` | Admin only | Today numbers, 30-day revenue and the two chart series. |
| GET | `/api/admin/payments` | Admin only | Every payment, newest first, with its refunds and the totals of what matches. |
| GET | `/api/admin/reports` | Admin only | Bookings by status, no-shows, revenue (booking fees, energy, walk-ins), refunds and operator settlement. |
| GET | `/api/admin/stations` | Admin only | Stations |
| GET | `/api/admin/stations/{station_id}` | Admin only | Get Station |
| PATCH | `/api/admin/stations/{station_id}` | Admin only | Edit a station. Taking it off the map while it has future bookings needs `cancel_bookings = true` (409 HAS_FUTURE_BOOKINGS otherwise). |
| POST | `/api/admin/stations/{station_id}/chargers` | Admin only | Create Charger |
| GET | `/api/admin/users` | Admin only | Users |
| PATCH | `/api/admin/users/{user_id}/role` | Admin only | Make an account an admin, or an ordinary driver again. You cannot change your own role, and the last admin cannot be removed. |

## Endpoints by area

### Health

#### `GET /health`

Health

**Auth:** Public

**Responses**

- **200** Successful Response: no body

### Authentication

#### `POST /auth/google`

Google Id Token Login

**Auth:** Public

**Request body** (`application/json`): `GoogleLoginRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `credential` | string | yes |  |

**Responses**

- **200** Successful Response: `TokenResponse`

#### `GET /auth/google/callback`

Google Callback

**Auth:** Public (checks the `state` cookie, then redirects to the web app with `#token=...`)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `code` | query | string | yes |  |
| `state` | query | string or null | no |  |
| `chargespot_oauth_state` | cookie | string or null | no |  |

**Responses**

- **200** Successful Response: no body

#### `GET /auth/google/login`

Google Login Redirect

**Auth:** Public (starts the Google redirect flow; sets a random `state` cookie)

**Responses**

- **200** Successful Response: no body

#### `POST /auth/login`

Login

**Auth:** Public

**Request body** (`application/json`): `UserLogin`

| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | string | yes |  |
| `password` | string | yes |  |

**Responses**

- **200** Successful Response: `TokenResponse`

#### `GET /auth/me`

Get Me

**Auth:** Login required (Bearer token)

**Responses**

- **200** Successful Response: `UserResponse`

#### `POST /auth/register`

Register

**Auth:** Public

**Request body** (`application/json`): `UserRegister`

| Field | Type | Required | Notes |
|---|---|---|---|
| `full_name` | string | yes |  |
| `email` | string | yes |  |
| `password` | string | yes |  |

**Responses**

- **201** Successful Response: `TokenResponse`

### Authentication API

#### `POST /api/auth/google`

Google Id Token Login

**Auth:** Public

**Request body** (`application/json`): `GoogleLoginRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `credential` | string | yes |  |

**Responses**

- **200** Successful Response: `TokenResponse`

#### `GET /api/auth/google/callback`

Google Callback

**Auth:** Public (same as `/auth/google/callback`)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `code` | query | string | yes |  |
| `state` | query | string or null | no |  |
| `chargespot_oauth_state` | cookie | string or null | no |  |

**Responses**

- **200** Successful Response: no body

#### `GET /api/auth/google/login`

Google Login Redirect

**Auth:** Public (same as `/auth/google/login`)

**Responses**

- **200** Successful Response: no body

### Stations

#### `GET /api/stations`

Search Stations

**Auth:** Public

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `bbox` | query | string or null | no | Map area: min_lng,min_lat,max_lng,max_lat |
| `lat` | query | number (>= -90, <= 90) or null | no | Search point: sorts by distance |
| `lng` | query | number (>= -180, <= 180) or null | no |  |
| `radius_km` | query | number (<= 100.0, > 0) or null | no | With lat/lng: only stations this near |
| `connector` | query | list of one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` | no | Plug types; a station matches if it has any |
| `min_power_kw` | query | number (> 0) or null | no | Only chargers at least this fast |
| `max_price` | query | number (> 0) or null | no | Only chargers at most this price per kWh (INR) |
| `operator` | query | string (min length 1, max length 120) or null | no | Only this operator's stations |
| `open_now` | query | boolean | no | Hide stations known to be closed right now |
| `limit` | query | integer (>= 1, <= 500) | no |  |

**Responses**

- **200** Successful Response: `StationSearchResponse`

#### `POST /api/stations`

Create Station

**Auth:** Admin only (Bearer token, role ADMIN)

**Request body** (`application/json`): `StationCreate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string (min length 1) | yes |  |
| `address` | string | no |  |
| `city` | string or null | no |  |
| `latitude` | number (>= -90.0, <= 90.0) | yes |  |
| `longitude` | number (>= -180.0, <= 180.0) | yes |  |
| `operator_id` | string (uuid) or null | no |  |

**Responses**

- **201** Successful Response: `StationDetail`

#### `GET /api/stations/count`

How many stations are on the map (shown on the landing page).

**Auth:** Public

**Responses**

- **200** Successful Response: `app__features__stations__schemas__StationCount`

#### `GET /api/stations/{station_id}`

Get Station

**Auth:** Public

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | path | string (uuid) | yes |  |
| `lat` | query | number (>= -90, <= 90) or null | no |  |
| `lng` | query | number (>= -180, <= 180) or null | no |  |

**Responses**

- **200** Successful Response: `StationDetail`

### Availability

#### `GET /api/stations/{station_id}/availability`

Get Availability

**Auth:** Public

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | path | string (uuid) | yes |  |
| `date` | query | string (date) or null | no | India-time day, YYYY-MM-DD (default: today) |

**Responses**

- **200** Successful Response: `StationAvailability`

### Search

#### `GET /api/search/suggest`

Suggest

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `q` | query | string (max length 80) | yes | What the user typed, e.g. 'tata power' |
| `lat` | query | number (>= -90, <= 90) or null | no | With lng: nearer stations rank higher |
| `lng` | query | number (>= -180, <= 180) or null | no |  |

**Responses**

- **200** Successful Response: `SuggestResponse`

### Recommendations

#### `GET /api/recommendations`

Get Recommendations

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `lat` | query | number (>= -90, <= 90) | yes | Where the driver is (or the map centre) |
| `lng` | query | number (>= -180, <= 180) | yes |  |
| `connector` | query | list of one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` | no | Plug types the car can use; empty = any |
| `start` | query | string (date-time) or null | no | When charging should start (default: now) |
| `duration` | query | integer | no | Minutes, in steps of 30 |

**Responses**

- **200** Successful Response: `RecommendationResponse`

### Geocoding

#### `GET /api/geocode`

Geocode

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `q` | query | string (min length 2, max length 200) | yes | A place, e.g. 'Bopal, Ahmedabad' |

**Responses**

- **200** Successful Response: `GeocodeResponse`

### Vehicles

#### `GET /api/me/vehicles`

List Vehicles

**Auth:** Login required (Bearer token)

**Responses**

- **200** Successful Response: list of `VehicleOut`

#### `POST /api/me/vehicles`

Add Vehicle

**Auth:** Login required (Bearer token)

**Request body** (`application/json`): `VehicleIn`

| Field | Type | Required | Notes |
|---|---|---|---|
| `nickname` | string (min length 1, max length 40) | yes | e.g. 'Tata Nexon EV' |
| `connector_type` | one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` | yes |  |
| `battery_kwh` | number (<= 250.0, > 0.0) | yes | Usable battery size in kWh |
| `is_default` | boolean | no | Default: `False`. |

**Responses**

- **201** Successful Response: `VehicleOut`

#### `DELETE /api/me/vehicles/{vehicle_id}`

Delete Vehicle

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `vehicle_id` | path | string (uuid) | yes |  |

**Responses**

- **204** Successful Response: no body

#### `PATCH /api/me/vehicles/{vehicle_id}`

Change Vehicle

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `vehicle_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `VehicleUpdate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `nickname` | string (min length 1, max length 40) or null | no |  |
| `connector_type` | one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` or null | no |  |
| `battery_kwh` | number (<= 250.0, > 0.0) or null | no |  |
| `is_default` | boolean or null | no |  |

**Responses**

- **200** Successful Response: `VehicleOut`

### Bookings

#### `POST /api/bookings`

Hold a slot for 5 minutes. Pay the fee in that time (POST /api/payments/orders) to confirm it.

**Auth:** Login required (Bearer token)

**Request body** (`application/json`): `BookingCreate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `charger_id` | string (uuid) | yes |  |
| `start` | string (date-time) | yes | When the slot starts: on a :00 or :30 boundary, in the future, within 7 days |
| `blocks` | integer (>= 1.0, <= 4.0) | yes | How many 30-minute blocks (1-4) |
| `vehicle_id` | string (uuid) or null | no |  |

**Responses**

- **201** Successful Response: `BookingOut`
- **409** SLOT_TAKEN (with alternatives), ACTIVE_HOLD_EXISTS or UNPAID_BILL: `SlotTakenResponse`

#### `POST /api/bookings/instant`

"Charge now" on a free charger: no fee, confirmed at once, the code is in this response (once).

**Auth:** Login required (Bearer token)

**Request body** (`application/json`): `InstantCreate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `charger_id` | string (uuid) | yes |  |
| `vehicle_id` | string (uuid) or null | no |  |

**Responses**

- **201** Successful Response: `InstantBookingOut`
- **409** CHARGER_BUSY, NO_ROOM_FOR_INSTANT, UNPAID_BILL or SLOT_TAKEN (with alternatives): `SlotTakenResponse`

#### `GET /api/bookings/{booking_id}`

Get Booking

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `booking_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `BookingOut`

#### `POST /api/bookings/{booking_id}/cancel`

Cancel Booking

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `booking_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `RefundPreview`

#### `GET /api/bookings/{booking_id}/cancel-preview`

What you would get back if you cancelled right now (nothing changes).

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `booking_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `RefundPreview`

#### `POST /api/bookings/{booking_id}/otp`

A new one-time code. The old one stops working.

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `booking_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `OtpOut`

#### `GET /api/me/bookings`

My Bookings

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `scope` | query | one of `upcoming`, `past` | no |  |

**Responses**

- **200** Successful Response: list of `BookingOut`

#### `GET /api/me/dues`

Unpaid energy bills. While there are any, new bookings are refused (UNPAID_BILL).

**Auth:** Login required (Bearer token)

**Responses**

- **200** Successful Response: `DuesOut`

### Payments

#### `POST /api/payments/orders`

The ₹199 booking-fee order for a held booking (the same order again if you ask twice).

**Auth:** Login required (Bearer token)

**Request body** (`application/json`): `OrderRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `booking_id` | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `OrderOut`

#### `POST /api/payments/verify`

Check Razorpay's signature, confirm the booking and return the one-time code (once).

**Auth:** Login required (Bearer token)

**Request body** (`application/json`): `VerifyRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `razorpay_order_id` | string (min length 1, max length 64) | yes |  |
| `razorpay_payment_id` | string (min length 1, max length 64) | yes |  |
| `razorpay_signature` | string (min length 1, max length 256) | yes |  |

**Responses**

- **200** Successful Response: `VerifyOut`

#### `POST /api/payments/webhook`

Called by Razorpay, not by the browser. The signature covers the raw body, so read it untouched.

**Auth:** Public, but checked: the `X-Razorpay-Signature` header must be a valid HMAC-SHA256 of the raw body with `RAZORPAY_WEBHOOK_SECRET`

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `x-razorpay-signature` | header | string | no |  |
| `x-razorpay-event-id` | header | string or null | no |  |

**Responses**

- **200** Successful Response: `WebhookAck`

### Charging

#### `GET /api/me/sessions/active`

The session that is charging right now, or null. Powers the Charging tab and the app-bar pill.

**Auth:** Login required (Bearer token)

**Responses**

- **200** Successful Response: `LiveSession` or null

#### `GET /api/me/sessions/{session_id}`

Live values: energy, battery level, cost so far, time left. Only the owner can see a session.

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `session_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `LiveSession`

#### `POST /api/me/sessions/{session_id}/pay`

The Razorpay order for this session's energy bill (the amount is the bill the server worked out).

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `session_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `EnergyOrderOut`

#### `POST /api/me/sessions/{session_id}/pay/verify`

Check Razorpay's signature, mark the bill paid and return the updated session.

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `session_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `VerifyRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `razorpay_order_id` | string (min length 1, max length 64) | yes |  |
| `razorpay_payment_id` | string (min length 1, max length 64) | yes |  |
| `razorpay_signature` | string (min length 1, max length 256) | yes |  |

**Responses**

- **200** Successful Response: `LiveSession`

#### `GET /api/me/sessions/{session_id}/receipt`

The receipt for a finished session (DUE bills show as unpaid).

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `session_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `ReceiptOut`

#### `POST /api/me/sessions/{session_id}/stop`

Stop charging now. The bill is worked out up to this moment.

**Auth:** Login required (Bearer token)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `session_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `LiveSession`

### Admin: simulator

#### `POST /api/admin/bookings/{booking_id}/start`

Demo stand-in for the kiosk: start charging for a confirmed booking as if its code was typed.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `booking_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `StartedSession`

#### `POST /api/admin/chargers/{charger_id}/simulate`

Make a charger behave like a real one: an outside start (refused while it is reserved), a stop,
an unplug, a fault or a recovery. A refusal is a normal answer (accepted = false), not an error.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `charger_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `SimulateRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | one of `EXTERNAL_START`, `EXTERNAL_STOP`, `FAULT`, `RECOVER`, `UNPLUG` | yes |  |

**Responses**

- **200** Successful Response: `SimulateResult`

### Kiosk

#### `POST /api/kiosk/otp-start`

Start the charger of the booking this code belongs to. 5 wrong tries in a row: 2 minutes' wait (429 OTP_COOLDOWN).

**Auth:** Kiosk device key (`X-Device-Key` header; the device sees only its own station)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `x-device-key` | header | string | no |  |

**Request body** (`application/json`): `OtpStartRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `otp` | string (min length 1, max length 12) | yes |  |

**Responses**

- **200** Successful Response: `OtpStartOut`

#### `GET /api/kiosk/status`

The status board: every charger's state, progress and free-until time. No names, phone numbers or bills.
The setup screen also calls this to check a pasted key.

**Auth:** Kiosk device key (`X-Device-Key` header; the device sees only its own station)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `x-device-key` | header | string | no |  |

**Responses**

- **200** Successful Response: `KioskStatus`

#### `POST /api/kiosk/walk-ins`

Take a free charger without a booking: holds it for 3 minutes and returns the payment link to show as a QR.

**Auth:** Kiosk device key (`X-Device-Key` header; the device sees only its own station)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `x-device-key` | header | string | no |  |

**Request body** (`application/json`): `WalkInCreate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `charger_id` | string (uuid) | yes |  |
| `amount` | integer (> 0.0) or null | no | One of the offered amounts, in rupees. |
| `until_next` | boolean | no | Default: `False`. |

**Responses**

- **201** Successful Response: `WalkInOut`

#### `GET /api/kiosk/walk-ins/{walk_in_id}`

Has the walk-in paid yet? Poll this while the QR is on screen.

**Auth:** Kiosk device key (`X-Device-Key` header; the device sees only its own station)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `walk_in_id` | path | string (uuid) | yes |  |
| `x-device-key` | header | string | no |  |

**Responses**

- **200** Successful Response: `WalkInOut`

#### `POST /api/kiosk/walk-ins/{walk_in_id}/cancel`

Back out of the QR screen: the charger is free again at once.

**Auth:** Kiosk device key (`X-Device-Key` header; the device sees only its own station)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `walk_in_id` | path | string (uuid) | yes |  |
| `x-device-key` | header | string | no |  |

**Responses**

- **200** Successful Response: `WalkInOut`

### Admin: kiosks

#### `POST /api/admin/devices/{device_id}/disable`

Switch a kiosk off (a lost tablet). Its key stops working at once.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `device_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `DeviceOut`

#### `GET /api/admin/stations/{station_id}/devices`

List Devices

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: list of `DeviceOut`

#### `POST /api/admin/stations/{station_id}/devices`

Create a kiosk key for a station. The key is in this response only; copy it to the tablet now.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `DeviceCreate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string (min length 1, max length 60) | yes | A label for the tablet, e.g. 'Entrance kiosk'. |

**Responses**

- **201** Successful Response: `DeviceCreated`

### Admin

#### `GET /api/admin/activity`

What admins changed, newest first.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `page` | query | integer (>= 1) | no |  |
| `page_size` | query | integer (>= 1, <= 100) | no |  |

**Responses**

- **200** Successful Response: `ActivityRows`

#### `GET /api/admin/alerts`

Alerts

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `include_seen` | query | boolean | no |  |

**Responses**

- **200** Successful Response: list of `AlertOut`

#### `POST /api/admin/alerts/{alert_id}/seen`

Alert Seen

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `alert_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `AlertOut`

#### `GET /api/admin/bookings`

Bookings by slot start (India-time days), newest first.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | query | string (uuid) or null | no |  |
| `status` | query | string or null | no |  |
| `date_from` | query | string (date) or null | no |  |
| `date_to` | query | string (date) or null | no |  |
| `page` | query | integer (>= 1) | no |  |
| `page_size` | query | integer (>= 1, <= 100) | no |  |

**Responses**

- **200** Successful Response: `BookingRows`

#### `GET /api/admin/bookings/{booking_id}/events`

The booking history: every status change, who made it and why.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `booking_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: list of `BookingEventOut`

#### `PATCH /api/admin/chargers/{charger_id}`

Edit a charger. Entering a power or price makes the value real: it loses its Approximate tag.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `charger_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `ChargerUpdate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `label` | string (min length 1, max length 40) or null | no |  |
| `connector_type` | one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` or null | no |  |
| `current_type` | one of `AC`, `DC` or null | no |  |
| `power_kw` | number (<= 1000.0, > 0.0) or null | no |  |
| `price_per_kwh` | number (>= 0.0, <= 1000.0) or null | no |  |

**Responses**

- **200** Successful Response: `AdminStation`

#### `GET /api/admin/chargers/{charger_id}/affected`

What taking this charger out of service would break: the future bookings, and whether someone is charging.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `charger_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `AffectedOut`

#### `GET /api/admin/chargers/{charger_id}/events`

The newest charger events first (the simulator live log).

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `charger_id` | path | string (uuid) | yes |  |
| `limit` | query | integer (>= 1, <= 200) | no |  |

**Responses**

- **200** Successful Response: list of `ChargerEventOut`

#### `POST /api/admin/chargers/{charger_id}/out-of-service`

Take a charger out of service. With future bookings it needs `cancel_bookings = true` (409 HAS_FUTURE_BOOKINGS otherwise);
each is then cancelled with a full refund of what was paid.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `charger_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `OutOfServiceRequest`

| Field | Type | Required | Notes |
|---|---|---|---|
| `cancel_bookings` | boolean | no | Default: `False`. |

**Responses**

- **200** Successful Response: `OutOfServiceResult`

#### `POST /api/admin/chargers/{charger_id}/restore`

Put an out-of-service charger back in use.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `charger_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `OutOfServiceResult`

#### `GET /api/admin/devices`

Devices

**Auth:** Admin only (Bearer token, role ADMIN)

**Responses**

- **200** Successful Response: list of `DeviceRow`

#### `PATCH /api/admin/devices/{device_id}`

Rename Device

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `device_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `DeviceRename`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string (min length 1, max length 60) | yes |  |

**Responses**

- **200** Successful Response: `DeviceOut`

#### `POST /api/admin/devices/{device_id}/rotate`

A new key for the same tablet and station. The old key stops working at once; the new one is in this answer only.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `device_id` | path | string (uuid) | yes |  |

**Responses**

- **201** Successful Response: `DeviceCreated`

#### `GET /api/admin/operators`

Operators

**Auth:** Admin only (Bearer token, role ADMIN)

**Responses**

- **200** Successful Response: list of `OperatorRow`

#### `POST /api/admin/operators`

Create Operator

**Auth:** Admin only (Bearer token, role ADMIN)

**Request body** (`application/json`): `OperatorIn`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string (min length 1, max length 120) | yes |  |
| `website` | string (max length 300) or null | no |  |

**Responses**

- **201** Successful Response: `OperatorRow`

#### `DELETE /api/admin/operators/{operator_id}`

Only an operator with no stations can be deleted (409 OPERATOR_IN_USE otherwise).

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `operator_id` | path | string (uuid) | yes |  |

**Responses**

- **204** Successful Response: no body

#### `PATCH /api/admin/operators/{operator_id}`

Update Operator

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `operator_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `OperatorUpdate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string (min length 1, max length 120) or null | no |  |
| `website` | string (max length 300) or null | no |  |

**Responses**

- **200** Successful Response: `OperatorRow`

#### `GET /api/admin/overview`

Today numbers, 30-day revenue and the two chart series.

**Auth:** Admin only (Bearer token, role ADMIN)

**Responses**

- **200** Successful Response: `OverviewOut`

#### `GET /api/admin/payments`

Every payment, newest first, with its refunds and the totals of what matches.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `purpose` | query | one of `BOOKING_FEE`, `ENERGY`, `WALKIN_PREPAID` or null | no |  |
| `status` | query | one of `CREATED`, `CAPTURED`, `FAILED`, `REFUNDED`, `PARTIALLY_REFUNDED` or null | no |  |
| `page` | query | integer (>= 1) | no |  |
| `page_size` | query | integer (>= 1, <= 100) | no |  |

**Responses**

- **200** Successful Response: `PaymentRows`

#### `GET /api/admin/reports`

Bookings by status, no-shows, revenue (booking fees, energy, walk-ins), refunds and operator settlement.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `date_from` | query | string (date) or null | no | First day, India time. Default: 30 days ago. |
| `date_to` | query | string (date) or null | no | Last day, India time. Default: today. |

**Responses**

- **200** Successful Response: `ReportOut`

#### `GET /api/admin/stations`

Stations

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `q` | query | string (max length 100) or null | no | Part of a station, city or operator name |
| `sort` | query | string | no | name, city, operator, source, chargers or status |
| `direction` | query | one of `asc`, `desc` | no |  |
| `active` | query | boolean or null | no | Only active (true) or inactive (false) stations |
| `page` | query | integer (>= 1) | no |  |
| `page_size` | query | integer (>= 1, <= 100) | no |  |

**Responses**

- **200** Successful Response: `StationRows`

#### `GET /api/admin/stations/{station_id}`

Get Station

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | path | string (uuid) | yes |  |

**Responses**

- **200** Successful Response: `AdminStation`

#### `PATCH /api/admin/stations/{station_id}`

Edit a station. Taking it off the map while it has future bookings needs `cancel_bookings = true` (409 HAS_FUTURE_BOOKINGS otherwise).

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `StationUpdate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string (min length 1, max length 160) or null | no |  |
| `address` | string (max length 300) or null | no |  |
| `city` | string (max length 120) or null | no |  |
| `latitude` | number (>= -90.0, <= 90.0) or null | no |  |
| `longitude` | number (>= -180.0, <= 180.0) or null | no |  |
| `operator_id` | string (uuid) or null | no |  |
| `opening_hours` | string (max length 300) or null | no |  |
| `is_active` | boolean or null | no |  |
| `cancel_bookings` | boolean | no | Default: `False`. |

**Responses**

- **200** Successful Response: `AdminStation`

#### `POST /api/admin/stations/{station_id}/chargers`

Create Charger

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `station_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `ChargerCreate`

| Field | Type | Required | Notes |
|---|---|---|---|
| `label` | string (min length 1, max length 40) | yes |  |
| `connector_type` | one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` | yes |  |
| `current_type` | one of `AC`, `DC` or null | no |  |
| `power_kw` | number (<= 1000.0, > 0.0) or null | no |  |
| `price_per_kwh` | number (>= 0.0, <= 1000.0) or null | no |  |

**Responses**

- **201** Successful Response: `AdminStation`

#### `GET /api/admin/users`

Users

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `q` | query | string (max length 100) or null | no | Part of an email or name |
| `role` | query | one of `USER`, `ADMIN` or null | no |  |
| `page` | query | integer (>= 1) | no |  |
| `page_size` | query | integer (>= 1, <= 100) | no |  |

**Responses**

- **200** Successful Response: `UserRows`

#### `PATCH /api/admin/users/{user_id}/role`

Make an account an admin, or an ordinary driver again. You cannot change your own role, and the last admin cannot be removed.

**Auth:** Admin only (Bearer token, role ADMIN)

**Parameters**

| Name | In | Type | Required | Notes |
|---|---|---|---|---|
| `user_id` | path | string (uuid) | yes |  |

**Request body** (`application/json`): `RoleChange`

| Field | Type | Required | Notes |
|---|---|---|---|
| `role` | one of `USER`, `ADMIN` | yes |  |

**Responses**

- **200** Successful Response: `UserRow`

## Response shapes

Fields of the main response models, in the order the API returns them.

### `TokenResponse`

| Field | Type | Required | Notes |
|---|---|---|---|
| `access_token` | string | yes |  |
| `token_type` | string | no | Default: `bearer`. |
| `user` | `UserResponse` | yes |  |

### `UserResponse`

| Field | Type | Required | Notes |
|---|---|---|---|
| `user_id` | string (uuid) | yes |  |
| `email` | string | yes |  |
| `full_name` | string or null | no |  |
| `phone` | string or null | no |  |
| `google_user_id` | string or null | no |  |
| `role` | string | no | Default: `USER`. |
| `created_at` | string (date-time) or null | no |  |

### `StationSummary`

| Field | Type | Required | Notes |
|---|---|---|---|
| `station_id` | string (uuid) | yes |  |
| `name` | string | yes |  |
| `address` | string | yes |  |
| `city` | string or null | no |  |
| `latitude` | number | yes |  |
| `longitude` | number | yes |  |
| `operator_name` | string or null | no |  |
| `vehicle_category` | string | yes |  |
| `opening_hours` | string or null | no |  |
| `is_open_now` | boolean or null | no |  |
| `rating` | number or null | no |  |
| `rating_is_estimated` | boolean | no | Default: `False`. |
| `rating_count` | integer | no | Default: `0`. |
| `data_source` | string | yes |  |
| `has_estimated_data` | boolean | yes |  |
| `charger_total` | integer | yes |  |
| `charger_free` | integer | yes |  |
| `connector_types` | list of one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` or string | yes |  |
| `min_power_kw` | number or null | no |  |
| `max_power_kw` | number or null | no |  |
| `min_price_per_kwh` | number or null | no |  |
| `distance_km` | number or null | no |  |
| `eta_minutes_estimate` | integer or null | no |  |

### `StationDetail`

| Field | Type | Required | Notes |
|---|---|---|---|
| `station_id` | string (uuid) | yes |  |
| `name` | string | yes |  |
| `address` | string | yes |  |
| `city` | string or null | no |  |
| `latitude` | number | yes |  |
| `longitude` | number | yes |  |
| `operator_name` | string or null | no |  |
| `vehicle_category` | string | yes |  |
| `opening_hours` | string or null | no |  |
| `is_open_now` | boolean or null | no |  |
| `rating` | number or null | no |  |
| `rating_is_estimated` | boolean | no | Default: `False`. |
| `rating_count` | integer | no | Default: `0`. |
| `data_source` | string | yes |  |
| `has_estimated_data` | boolean | yes |  |
| `charger_total` | integer | yes |  |
| `charger_free` | integer | yes |  |
| `connector_types` | list of one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` or string | yes |  |
| `min_power_kw` | number or null | no |  |
| `max_power_kw` | number or null | no |  |
| `min_price_per_kwh` | number or null | no |  |
| `distance_km` | number or null | no |  |
| `eta_minutes_estimate` | integer or null | no |  |
| `chargers` | list of `ChargerDetail` | yes |  |

### `ChargerDetail`

| Field | Type | Required | Notes |
|---|---|---|---|
| `charger_id` | string (uuid) | yes |  |
| `label` | string | yes |  |
| `connector_type` | string | yes |  |
| `current_type` | string or null | no |  |
| `power_kw` | number or null | no |  |
| `price_per_kwh` | number or null | no |  |
| `status` | string | yes |  |
| `free_now` | boolean | yes |  |
| `data_source` | string | yes |  |
| `is_estimated` | boolean | yes |  |
| `estimated_fields` | list of string | no |  |

### `StationSearchResponse`

| Field | Type | Required | Notes |
|---|---|---|---|
| `stations` | list of `StationSummary` | yes |  |
| `count` | integer | yes |  |
| `limit` | integer | yes |  |
| `truncated` | boolean | yes |  |

### `StationAvailability`

| Field | Type | Required | Notes |
|---|---|---|---|
| `station_id` | string (uuid) | yes |  |
| `date` | string (date) | yes |  |
| `timezone` | string | yes |  |
| `slot_minutes` | integer | yes |  |
| `now` | string (date-time) | yes |  |
| `chargers` | list of `ChargerAvailability` | yes |  |

### `ChargerAvailability`

| Field | Type | Required | Notes |
|---|---|---|---|
| `charger_id` | string (uuid) | yes |  |
| `label` | string | yes |  |
| `connector_type` | string | yes |  |
| `power_kw` | number or null | no |  |
| `price_per_kwh` | number or null | no |  |
| `status` | string | yes |  |
| `is_estimated` | boolean | yes |  |
| `blocks` | list of `AvailabilityBlock` | yes |  |

### `AvailabilityBlock`

| Field | Type | Required | Notes |
|---|---|---|---|
| `start` | string (date-time) | yes |  |
| `end` | string (date-time) | yes |  |
| `state` | one of `FREE`, `BOOKED`, `HELD`, `PAST`, `OUT_OF_SERVICE`, `BUSY_EXTERNAL` | yes |  |

### `Recommendation`

| Field | Type | Required | Notes |
|---|---|---|---|
| `station` | `StationSummary` | yes |  |
| `score` | number | yes |  |
| `reason` | string | yes |  |
| `free_compatible` | integer | yes |  |
| `travel_minutes` | number | yes |  |
| `travel_is_routed` | boolean | yes |  |
| `distance_km` | number | yes |  |

### `SuggestResponse`

| Field | Type | Required | Notes |
|---|---|---|---|
| `query` | string | yes |  |
| `stations` | list of `StationSummary` | yes |  |
| `operators` | list of `AreaSuggestion` | yes |  |
| `cities` | list of `AreaSuggestion` | yes |  |
| `did_you_mean` | string or null | no |  |

### `VehicleOut`

| Field | Type | Required | Notes |
|---|---|---|---|
| `vehicle_id` | string (uuid) | yes |  |
| `nickname` | string | yes |  |
| `connector_type` | one of `CCS2`, `TYPE2`, `CHADEMO`, `BHARAT_AC001`, `BHARAT_DC001`, `TYPE1`, `OTHER` or string | yes |  |
| `battery_kwh` | number | yes |  |
| `is_default` | boolean | yes |  |
| `created_at` | string (date-time) or null | no |  |

### `BookingOut`

| Field | Type | Required | Notes |
|---|---|---|---|
| `booking_id` | string (uuid) | yes |  |
| `status` | string | yes |  |
| `source` | string | yes |  |
| `start` | string (date-time) | yes |  |
| `end` | string (date-time) | yes |  |
| `blocks` | integer | yes |  |
| `hold_expires_at` | string (date-time) or null | no |  |
| `server_time` | string (date-time) | yes |  |
| `booking_fee` | number | yes |  |
| `fee_paid` | boolean | yes |  |
| `refund_amount` | number | yes |  |
| `cancelled_at` | string (date-time) or null | no |  |
| `cancel_reason` | string or null | no |  |
| `created_at` | string (date-time) or null | no |  |
| `station` | `BookingStation` | yes |  |
| `charger` | `BookingCharger` | yes |  |
| `code_valid_from` | string (date-time) | yes |  |
| `code_valid_until` | string (date-time) | yes |  |
| `has_code` | boolean | yes |  |
| `code_used` | boolean | yes |  |
| `can_cancel` | boolean | yes |  |
| `can_show_new_code` | boolean | yes |  |
| `notice_kind` | string or null | no |  |
| `notice_text` | string or null | no |  |
| `session_id` | string (uuid) or null | no |  |

### `InstantBookingOut`

| Field | Type | Required | Notes |
|---|---|---|---|
| `booking_id` | string (uuid) | yes |  |
| `status` | string | yes |  |
| `source` | string | yes |  |
| `start` | string (date-time) | yes |  |
| `end` | string (date-time) | yes |  |
| `blocks` | integer | yes |  |
| `hold_expires_at` | string (date-time) or null | no |  |
| `server_time` | string (date-time) | yes |  |
| `booking_fee` | number | yes |  |
| `fee_paid` | boolean | yes |  |
| `refund_amount` | number | yes |  |
| `cancelled_at` | string (date-time) or null | no |  |
| `cancel_reason` | string or null | no |  |
| `created_at` | string (date-time) or null | no |  |
| `station` | `BookingStation` | yes |  |
| `charger` | `BookingCharger` | yes |  |
| `code_valid_from` | string (date-time) | yes |  |
| `code_valid_until` | string (date-time) | yes |  |
| `has_code` | boolean | yes |  |
| `code_used` | boolean | yes |  |
| `can_cancel` | boolean | yes |  |
| `can_show_new_code` | boolean | yes |  |
| `notice_kind` | string or null | no |  |
| `notice_text` | string or null | no |  |
| `session_id` | string (uuid) or null | no |  |
| `otp` | string | yes |  |

### `OtpOut`

| Field | Type | Required | Notes |
|---|---|---|---|
| `booking_id` | string (uuid) | yes |  |
| `otp` | string | yes |  |
| `valid_from` | string (date-time) | yes |  |
| `valid_until` | string (date-time) | yes |  |
| `note` | string | no | Default: `This code is shown once. Showing a new code makes this one stop working.`. |

### `RefundPreview`

| Field | Type | Required | Notes |
|---|---|---|---|
| `booking_id` | string (uuid) | yes |  |
| `fee_paid` | number | yes |  |
| `refund_amount` | number | yes |  |
| `percent` | integer | yes |  |
| `reason` | string | yes |  |

### `Alternatives`

| Field | Type | Required | Notes |
|---|---|---|---|
| `charger_id` | string (uuid) | yes |  |
| `blocks` | integer | yes |  |
| `same_charger` | list of `SlotAlternative` | yes |  |
| `other_chargers` | list of `ChargerAlternative` | yes |  |
| `stations` | list of `StationAlternative` | yes |  |

### `DuesOut`

| Field | Type | Required | Notes |
|---|---|---|---|
| `count` | integer | yes |  |
| `total` | number | yes |  |
| `items` | list of `DueItem` | yes |  |

### `OrderOut`

| Field | Type | Required | Notes |
|---|---|---|---|
| `booking_id` | string (uuid) | yes |  |
| `order_id` | string | yes |  |
| `amount` | number | yes |  |
| `amount_paise` | integer | yes |  |
| `currency` | string | yes |  |
| `key_id` | string | yes |  |
| `hold_expires_at` | string (date-time) | yes |  |
| `checkout_timeout_seconds` | integer | yes |  |

### `VerifyOut`

| Field | Type | Required | Notes |
|---|---|---|---|
| `outcome` | string | yes |  |
| `booking` | `BookingOut` | yes |  |
| `otp` | string or null | no | Shown ONCE. Null when the code was already issued or the booking was refunded. |
| `refund_amount` | number | no | Default: `0`. |
| `message` | string | yes |  |

### `LiveSession`

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string (uuid) | yes |  |
| `booking_id` | string (uuid) or null | no |  |
| `status` | one of `RUNNING`, `ENDED` | yes |  |
| `source` | string | yes |  |
| `station` | `BookingStation` | yes |  |
| `charger` | `BookingCharger` | yes |  |
| `started_at` | string (date-time) | yes |  |
| `planned_stop_at` | string (date-time) or null | no |  |
| `server_time` | string (date-time) | yes |  |
| `seconds_left` | integer or null | no |  |
| `energy_kwh` | number | yes |  |
| `battery_percent` | number | yes |  |
| `cost_so_far` | number | yes |  |
| `ended_at` | string (date-time) or null | no |  |
| `end_reason` | string or null | no |  |
| `duration_minutes` | number | yes |  |
| `bill_amount` | number or null | no |  |
| `bill_status` | string or null | no |  |
| `stop_warning` | boolean | no | Default: `False`. |
| `next_booking_waiting` | boolean | no | Default: `False`. |
| `can_stop` | boolean | no | Default: `False`. |

### `SimulateResult`

| Field | Type | Required | Notes |
|---|---|---|---|
| `accepted` | boolean | yes |  |
| `status` | string | yes |  |
| `reason` | string or null | no |  |
| `session_id` | string (uuid) or null | no |  |

### `StartedSession`

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string (uuid) | yes |  |
| `booking_id` | string (uuid) | yes |  |
| `charger_id` | string (uuid) | yes |  |

### `WebhookAck`

| Field | Type | Required | Notes |
|---|---|---|---|
| `status` | string | yes |  |

## Error codes

Raised with `AppError(status, code, message)`; the front end reacts to `code`. Plain `HTTPException`s (used by the auth code) are mapped to a code by status in `backend/app/core/errors.py` (`401 UNAUTHORIZED`, `403 FORBIDDEN`, ...).

| Code | Status | Raised in |
|---|---|---|
| `INVALID_AMOUNT` | 400 | `app/features/kiosk/walkin.py` |
| `INVALID_PAYLOAD` | 400 | `app/features/payments/service.py` |
| `INVALID_SIGNATURE` | 400 | `app/features/payments/service.py` |
| `WRONG_OTP` | 400 | `app/features/kiosk/service.py` |
| `INVALID_DEVICE_KEY` | 401 | `app/features/kiosk/dependencies.py` |
| `DEVICE_DISABLED` | 403 | `app/features/kiosk/dependencies.py` |
| `ALERT_NOT_FOUND` | 404 | `app/features/admin/service.py` |
| `BOOKING_NOT_FOUND` | 404 | `app/features/admin/service.py`, `app/features/bookings/service.py`, `app/features/charging/service.py`, `app/features/payments/service.py` |
| `CHARGER_NOT_FOUND` | 404 | `app/features/admin/service.py`, `app/features/bookings/service.py`, `app/features/chargers/service.py`, `app/features/kiosk/walkin.py` |
| `DEVICE_NOT_FOUND` | 404 | `app/features/admin/manage.py`, `app/features/kiosk/admin_router.py` |
| `NO_RECEIPT` | 404 | `app/features/charging/receipt.py` |
| `OPERATOR_NOT_FOUND` | 404 | `app/features/admin/manage.py` |
| `PAYMENT_NOT_FOUND` | 404 | `app/features/payments/service.py` |
| `SESSION_NOT_FOUND` | 404 | `app/features/charging/service.py`, `app/features/payments/service.py` |
| `STATION_NOT_FOUND` | 404 | `app/features/admin/service.py`, `app/features/availability/service.py`, `app/features/kiosk/admin_router.py`, `app/features/stations/service.py` |
| `USER_NOT_FOUND` | 404 | `app/features/admin/manage.py` |
| `VEHICLE_NOT_FOUND` | 404 | `app/features/vehicles/service.py` |
| `WALK_IN_NOT_FOUND` | 404 | `app/features/kiosk/walkin.py` |
| `ACTIVE_HOLD_EXISTS` | 409 | `app/features/bookings/service.py` |
| `BILL_ALREADY_PAID` | 409 | `app/features/payments/service.py` |
| `BOOKING_NOT_PAYABLE` | 409 | `app/features/payments/service.py` |
| `BOOKING_NOT_STARTABLE` | 409 | `app/features/charging/service.py` |
| `CANNOT_CANCEL` | 409 | `app/features/bookings/service.py` |
| `CANNOT_CHANGE_OWN_ROLE` | 409 | `app/features/admin/manage.py` |
| `CHARGER_BUSY` | 409 | `app/features/bookings/service.py`, `app/features/kiosk/walkin.py` |
| `CHARGER_LABEL_TAKEN` | 409 | `app/features/admin/service.py` |
| `CHARGER_OUT_OF_SERVICE` | 409 | `app/features/bookings/service.py` |
| `CHARGER_UNAVAILABLE` | 409 | `app/features/charging/service.py`, `app/features/kiosk/walkin.py` |
| `CODE_ALREADY_USED` | 409 | `app/features/bookings/service.py` |
| `CODE_WINDOW_ENDED` | 409 | `app/features/bookings/service.py` |
| `DEFAULT_REQUIRED` | 409 | `app/features/vehicles/service.py` |
| `DEVICE_REVOKED` | 409 | `app/features/admin/manage.py` |
| `HAS_FUTURE_BOOKINGS` | 409 | `app/features/admin/service.py` |
| `HOLD_EXPIRED` | 409 | `app/features/payments/service.py` |
| `ILLEGAL_STATUS_CHANGE` | 409 | `app/features/bookings/state_machine.py` |
| `LAST_ADMIN` | 409 | `app/features/admin/manage.py` |
| `NOT_OUT_OF_SERVICE` | 409 | `app/features/admin/service.py` |
| `NO_BILL_DUE` | 409 | `app/features/payments/service.py` |
| `NO_CODE_FOR_STATUS` | 409 | `app/features/bookings/service.py` |
| `NO_ROOM_FOR_INSTANT` | 409 | `app/features/bookings/service.py` |
| `NO_ROOM_FOR_WALK_IN` | 409 | `app/features/kiosk/walkin.py` |
| `OPERATOR_IN_USE` | 409 | `app/features/admin/manage.py` |
| `OPERATOR_NAME_TAKEN` | 409 | `app/features/admin/manage.py` |
| `OTP_NOT_VALID_NOW` | 409 | `app/features/kiosk/service.py` |
| `PRICE_UNKNOWN` | 409 | `app/features/kiosk/walkin.py` |
| `SESSION_NOT_ENDED` | 409 | `app/features/charging/receipt.py`, `app/features/payments/service.py` |
| `SLOT_TAKEN` | 409 | `app/features/bookings/service.py` |
| `TOO_MANY_VEHICLES` | 409 | `app/features/vehicles/service.py` |
| `UNPAID_BILL` | 409 | `app/features/bookings/service.py` |
| `DATE_OUT_OF_RANGE` | 422 | `app/features/availability/service.py` |
| `INCOMPATIBLE_VEHICLE` | 422 | `app/features/bookings/service.py` |
| `INVALID_BBOX` | 422 | `app/features/stations/router.py` |
| `INVALID_BLOCKS` | 422 | `app/features/bookings/service.py` |
| `INVALID_DURATION` | 422 | `app/features/recommendations/service.py` |
| `INVALID_LOCATION` | 422 | `app/features/stations/router.py` |
| `INVALID_RANGE` | 422 | `app/features/admin/service.py` |
| `INVALID_SORT` | 422 | `app/features/admin/service.py` |
| `OPERATOR_NOT_FOUND` | 422 | `app/features/admin/service.py` |
| `QUERY_TOO_SHORT` | 422 | `app/features/geocoding/service.py`, `app/features/search/router.py` |
| `SLOT_NOT_ALIGNED` | 422 | `app/features/bookings/service.py` |
| `START_IN_PAST` | 422 | `app/features/bookings/service.py` |
| `START_TOO_FAR` | 422 | `app/features/bookings/service.py`, `app/features/recommendations/service.py` |
| `UNKNOWN_EVENT` | 422 | `app/features/chargers/service.py` |
| `OTP_COOLDOWN` | 429 | `app/features/kiosk/service.py` |
| `SEARCH_BUSY` | 429 | `app/features/geocoding/service.py` |
| `PAYMENT_PROVIDER_ERROR` | 502 | `app/features/payments/gateway.py` |
| `DATABASE_UNAVAILABLE` | 503 | `app/features/search/router.py`, `app/features/stations/router.py` |
| `GEOCODER_UNAVAILABLE` | 503 | `app/features/geocoding/service.py` |
| `OTP_UNAVAILABLE` | 503 | `app/features/bookings/otp.py` |
| `SETTING_MISSING` | 503 | `app/config.py` |

### Errors that carry `details`

| Code | `details` contains |
|---|---|
| `SLOT_TAKEN` | `alternatives`: `charger_id`, `blocks`, `same_charger` (other times), `other_chargers`, `stations` (see `Alternatives`) |
| `ACTIVE_HOLD_EXISTS` | `booking_id` of the hold the user already has |
| `UNPAID_BILL` | `count`, `total` of the unpaid energy bills |
