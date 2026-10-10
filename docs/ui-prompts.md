# ChargeSpot: UI Prompts for Claude Code

Ready-to-paste prompts that build ChargeSpot's interface, one per step of the UI build order in [ui-flow.md](ui-flow.md#8-build-order).

## How to use these

| UI step | When | Paste |
|---|---|---|
| **UI pass** | Now, before Phase 3 | Prompt U on its own |
| **Phase 3–7 UI** | During each phase | First the phase prompt from [phases.md](phases.md) (backend + data), then the matching UI prompt below. Or paste both together. |

Each UI prompt only covers **screens**. The API endpoints it calls are built by the phase prompt. If an endpoint is missing, the UI prompt tells Claude to stop and say so instead of faking data.

### Rules every UI prompt includes
1. Follow [ui-flow.md](ui-flow.md): "Midnight Charge" tokens, Material-style surfaces, **glass only over the map**, no gradient blobs, gradient text or emoji icons.
2. Build screens only from the shared components in `frontend/user-web/src/components/ui/` (created in the UI pass). If a needed component is missing, add it there, not inline.
3. Mobile first: check every screen at **375 px, 768 px and 1280 px** wide.
4. Accessibility: AA contrast, keyboard focus, labels on icon buttons, status = colour + text, `prefers-reduced-motion` respected.
5. Every data screen has **loading (skeleton), empty, error and success** states.
6. Never invent values on screen. Unknown shows as "—"/"Unknown"; estimated values show the **Approximate** tag.
7. No new npm dependency without asking first.
8. Login, routing and existing behaviour must keep working.
9. Finish by running `npm run build` and `npm run lint`, list what changed and what to check by hand, then **stop**.

---

## Prompt U: UI pass (theme, building blocks, navigation, Landing, Sign in, Profile shell)

**Owner:** C (with D). **Effort:** 3–4 person-days. **Branch:** `ui-foundation`.

```text
We are building ChargeSpot (a college final-year project, React 19 + Vite + TypeScript
+ Tailwind v4 in frontend/user-web). Read docs/ui-flow.md fully, then
docs/architecture.md sections 1 and 4 and CLAUDE.md. Do ONLY this UI pass. Do not
touch the backend or database. Create branch ui-foundation.

GOAL
Replace the current "glassmorphic / glowing" look with the agreed "Midnight Charge"
design system, build a reusable component library, a responsive app shell, and
polish the Landing, Sign in, Sign up and Profile screens. The station map page only
gets restyled with the new components; Phase 3 redesigns it.

1. DESIGN TOKENS (shared with the future kiosk app)
- Create frontend/shared/src/styles/tokens.css with the colour, radius, spacing,
  shadow (3 elevation levels) and motion tokens from docs/ui-flow.md section 1, as
  CSS variables, exposed to Tailwind v4 through @theme so classes like bg-surface,
  text-muted, border-border, bg-primary work. Import it from user-web's index.css.
- Font: Plus Jakarta Sans via a Google Fonts <link> in index.html (preconnect,
  display=swap, weights 500 and 700). No npm package. Add a utility for tabular numbers.
- Respect prefers-reduced-motion globally.
- Remove the old effects: glass-card, gradient-btn, gradient-text,
  electric-current-container/electric-inner-pill, glow blobs, conic borders.
  Every usage must be migrated; none of these classes may remain.

2. COMPONENT LIBRARY: frontend/user-web/src/components/ui/
Small, typed, documented with a short comment each:
- Button (variants: primary, secondary, ghost, danger; sizes sm/md/lg; loading state;
  optional leading icon; full-width option) and IconButton (aria-label required).
- Card (elevation 1/2), Divider.
- Badge and StatusBadge (Free / Few left / Busy / Offline: colour AND text).
- Chip (toggleable filter chip, aria-pressed).
- Field (label, hint, error message wiring via aria-describedby), TextInput, Select.
- Tabs (keyboard arrow navigation, aria roles).
- Skeleton (line, block, circle) and EmptyState (icon/illustration, title, text, one action).
- Toast system: ToastProvider + useToast() (success, error, info; auto-dismiss;
  aria-live polite; bottom on phone, bottom-right on desktop).
- Sheet: a bottom sheet on phones and a centred dialog on desktop, with focus trap,
  Esc to close, scroll lock, and focus returned to the trigger.
- ApproximateTag: dotted-outline "Approximate" tag with an accessible tooltip
  explaining why ("Price estimated from typical Tata Power tariffs").
- Money (uses formatINR from @chargespot/shared) and DateTime (uses formatIST;
  "Today, 4:30 PM" / "Tomorrow" / "Sun 13 Oct").
- ConnectorIcon: small inline SVG per connector type (CCS2, TYPE2, CHADEMO,
  BHARAT_AC001, BHARAT_DC001, TYPE1, OTHER), with the label from CONNECTOR_LABELS.
- Spinner (only for buttons; pages use skeletons).
Export everything from components/ui/index.ts.

3. DEV STYLE GUIDE
A /dev/ui route, only when import.meta.env.DEV, showing every component in every
variant and state, plus the colour tokens. The team uses it as a reference.

4. APP SHELL AND NAVIGATION
- PublicLayout (Landing, Sign in, Sign up): simple top bar with logo + Sign in.
- AppLayout (signed in): desktop slim top bar (logo, Explore, Bookings, Charging,
  Profile menu); phone bottom tab bar with the same four items (icons + labels,
  active state, safe-area padding). "Charging" shows as inactive for now; Phase 5
  makes it live.
- Routes: /explore (the current stations page, restyled), /dashboard redirects to
  /explore, signed-in visitors to / go to /explore, /bookings and /profile/vehicles
  as honest placeholder pages using EmptyState ("Your bookings will appear here").
  Keep ProtectedRoute behaviour.
- A slim "Reconnecting…" banner component, ready for later use.
- Footer: "Map data © OpenStreetMap contributors · Station data: Open Charge Map".

5. SCREENS
- Landing (/): headline "Book your EV charger before you arrive"; a large search
  field that sends the user to /explore?q=<text> (to sign in first if needed); a
  live line such as "84 stations across Gujarat" computed from GET /api/stations
  (skeleton while loading, hidden on error); a 4-step "How it works" strip (Find, Book,
  Enter code, Charge) with simple inline SVG illustrations; three honest
  "Why ChargeSpot" points; Sign in with Google call to action. No marketing filler.
- Sign in and Sign up: one centred card each. Google button first (Google Identity
  Services, dark theme), email form second, clear field errors via Field, loading
  state on submit. KEEP all existing auth logic and redirects exactly as they are.
- Profile (/profile): avatar initials, name, email, role badge for admins, links to
  Vehicles (placeholder) and Sign out.
- Explore (/explore): restyle only. Use Card, StatusBadge, Chip, Button, Money,
  ConnectorIcon and the new search field; replace the ⚡ emoji pin with an SVG icon;
  restyle Leaflet popups and zoom controls to the tokens. Keep its current layout and
  data logic; Phase 3 rebuilds it.

6. QUALITY
- Check every screen at 375, 768 and 1280 px: no horizontal scrolling, tap targets of
  at least 44 px.
- Keyboard-only walkthrough: Landing → Sign in → Explore → Profile → Sign out.
- npm run build and npm run lint pass; no new lint warnings.
- No new npm dependencies (ask first if you believe one is needed).

When finished: list every new component and screen, which old classes were removed,
and a short manual test checklist for me (what to click, at which widths). Then STOP
and wait for my review.
```

**Done when:** `/dev/ui` shows all components; the old glow/glass classes are gone; the bottom tabs work on phone; Landing, Sign in, Sign up and Profile match `ui-flow.md`; login still works; build and lint pass.

---

## Prompt 3-UI: Explore and Station page

**Run with:** Phase 3 prompt (`phases.md`). **Owner:** C. **Effort:** 3–4 person-days.

```text
We are building ChargeSpot. Read docs/ui-flow.md (sections 1, 2, 3 and 7),
docs/architecture.md section 12 and docs/phases.md Phase 3. The Phase 3 API
(GET /stations by bbox or radius, GET /stations/{id},
GET /stations/{id}/availability, GET /recommendations, GET /geocode) must exist. If
any endpoint is missing, stop and tell me instead of faking data. Use generated
types from @chargespot/shared (run npm run generate:api-types first) and only the
components in src/components/ui.

Build the UI for PHASE 3 ONLY: the Explore screen and the Station page (read-only grid).

EXPLORE (/explore)
- Phone: full-screen map with a draggable bottom sheet (three snap points: peek
  showing 1 card, half, full; drag handle; also opens with a tap; keyboard accessible).
  Desktop (≥1024 px): 400 px list panel on the left, map on the right.
- Floating glass search bar and filter chips over the map (the ONLY glass in the
  app): connector (multi-select), Fast 50 kW+, Open now, and "My car" when the user
  has a vehicle. Filters live in the URL (?connector=CCS2&fast=1) so views can be shared.
- Search: typing filters station names locally (no network per keystroke).
  Pressing Enter on a place name calls GET /geocode once and flies the map there.
  Show "No places found" and "Search unavailable" states.
- Map: default view Ahmedabad (23.0225, 72.5714, zoom 12). A "Locate me" button.
  Load stations for the visible area when the map stops moving (debounced). Pins show
  the number of free chargers, coloured green (2+), amber (1), rose (0), grey
  (offline). The selected pin is enlarged. Do NOT rebuild every marker on selection
  or filter changes: update only what changed. If pins overlap badly when zoomed
  out, ask me before adding leaflet.markercluster.
- "Best for you now" section at the top of the list, from GET /recommendations
  (user location or map centre, vehicle connector if known, start = now, 60 min):
  up to 3 cards with the reason text ("2 CCS2 free · 1.2 km · ₹18/kWh").
- Station cards: name, operator, distance and ETA, StatusBadge with free/total,
  ConnectorIcons, lowest price (Money), Approximate tag when has_estimated_data.
  Remove every invented fallback value ("3/4 available", "CCS2, Type 2"); show
  "Unknown" instead. Tapping a card selects the pin; a second tap opens the station page.
- States: skeleton cards while loading, EmptyState "No stations here, zoom out or
  clear filters", error card with Retry, and the location-denied hint.

STATION PAGE (/stations/:id)
- Header: name, operator, rating, distance and ETA, address, opening hours,
  Navigate (Google Maps directions deep link) and Share (navigator.share, falling
  back to copying the link with a toast). Back button returns to Explore with its
  previous view.
- Chargers: a card per charger (ConnectorIcon, label, kW, price, StatusBadge,
  Approximate tag when is_estimated).
- Availability grid (read-only in Phase 3): day tabs for today + 6 days ("Today",
  "Tomorrow", "Mon 14"); rows = chargers; columns = 30-minute blocks for the whole
  day, scrolling horizontally and auto-scrolled to "now" on today; sticky charger
  labels; a "now" line; legend (Free, Booked, Held, Past, Out of service). Block
  states come from the API, never computed in the browser. Each block has an
  accessible label ("CCS2-1, 4:30 to 5:00 PM, free"). Skeleton while loading.
- Leave clear hooks (props/handlers) for Phase 4 to make blocks selectable. Don't
  build selection now.

QUALITY
- Check at 375, 768 and 1280 px; bottom-sheet drag works with touch and mouse.
- Map interactions stay smooth with all Gujarat stations loaded.
- Approximate tags appear exactly where the API says data is estimated.
- npm run build and npm run lint pass. No new dependency without asking.

When finished: summarise the screens and states, list what I should check by hand
(including on a real phone), then STOP.
```

---

## Prompt 4-UI: Booking flow

**Run with:** Phase 4 prompt. **Owner:** C. **Effort:** 4–5 person-days.

```text
We are building ChargeSpot. Read docs/ui-flow.md (sections 3, 4, 5 and 7) and
docs/architecture.md sections 6, 7.1, 7.2 and 8. The Phase 4 API (bookings, instant
bookings, payments/verify, cancel with refund preview, new OTP, vehicles, my
bookings) must exist. If an endpoint is missing, stop and tell me. Use generated
types and src/components/ui only.

Build the UI for PHASE 4 ONLY.

1. INTERACTIVE SLOT GRID (station page)
- Make free blocks selectable: tap a start block and an end block, or drag on
  desktop; 1–4 contiguous blocks on ONE charger; keyboard (arrows + Space/Enter).
  Invalid choices (past, booked, crossing a booked block, more than 4) show a short
  inline message, not a crash.
- Sticky summary bar slides up: charger, "Sat 12 Oct · 4:30–5:30 PM", Booking fee
  ₹199, "Est. charging ₹486" (from charger power, price and the user's default
  vehicle battery; labelled "estimate"), and a "Hold & pay" button.
- "Charge now" button on rows whose charger is free right now (instant booking, no
  fee): confirm sheet → Ticket.
- If the user has an unpaid bill, disable booking and show the dues banner with a
  link to Bookings → Payment due.

2. HOLD & PAY (/book/:bookingId)
- Countdown ring driven by the server's hold_expires_at (never a client-only
  timer); turns amber under 1 minute.
- Summary card, "Pay ₹199" opens Razorpay Checkout (themed with the primary colour,
  prefilled name/email). Handle success (verify → Ticket), failure ("Payment didn't
  go through" + Try again, hold continues), dismissal, and expiry ("Hold expired,
  slot released" → back to the station with the selection kept).
- Cancel button releases the hold immediately.
- SLOT TAKEN: when the API returns SLOT_TAKEN, open a Sheet "Just taken. Here are
  alternatives" listing the API's alternatives (same charger nearby times, other
  chargers, nearby stations), each bookable in one tap.

3. TICKET (/tickets/:bookingId)
- Movie-ticket card: check mark, station, date and time, charger, a dashed tear
  line with notches, the OTP as six large digit tiles (tabular numbers, screen-reader
  friendly), "Valid from 4:15 PM", Navigate, and "Add to calendar" (generate an .ics
  file in the browser, no dependency).
- Clearly say the code is shown once; "Show new code" lives in Bookings.

4. BOOKINGS (/bookings)
- Tabs: Upcoming · Past · Payment due (with count badge).
- Ticket-style cards with a status timeline (Held → Confirmed → Charging → Done; or
  Cancelled / No-show / Expired) and actions by status:
  Upcoming: View ticket, Show new code (confirm sheet: the old code stops working),
  Navigate, Cancel.
  Cancel: Sheet with the refund preview from the API ("You'll get ₹149.25 back",
  which tier applies and why) → Confirm → toast.
  Past: receipt link when paid; "No-show · fee kept" badge.
- EmptyState per tab; skeletons; error with Retry.

5. VEHICLES (/profile/vehicles)
- List, add, edit, delete, set default. Form: nickname, connector (with
  ConnectorIcon), battery kWh, validated via Field. The default vehicle pre-fills the
  Explore connector filter and the cost estimate.

QUALITY
- Full keyboard path: pick slots → hold → pay (test mode) → ticket.
- Test with Razorpay's test UPI (success@razorpay) and a failing test card.
- Check at 375, 768 and 1280 px. npm run build and npm run lint pass.
  No new dependency without asking.

When finished: list the screens, every error state you handled, and a manual test
script (including a two-browser "slot just taken" test). Then STOP.
```

---

## Prompt 5-UI: Live charging and live updates

**Run with:** Phase 5 prompt. **Owner:** C. **Effort:** 2–3 person-days.

```text
We are building ChargeSpot. Read docs/ui-flow.md (sections 3, 5 and 7) and
docs/architecture.md sections 7.4, 10 and 11. The Phase 5 API (session details,
stop session, realtime nudges via Supabase, charger simulator) must exist. If
missing, stop and tell me. Use src/components/ui only.

Build the UI for PHASE 5 ONLY.

1. LIVE CHARGING (/charging/:sessionId)
- A large SVG battery ring showing charge % (the ONE glowing element in the app),
  with kWh delivered, cost so far (Money) and time left in tabular numbers below.
  Values come from the API (refresh on realtime nudge, plus every 15 s as a fallback);
  animate between values smoothly.
- Amber banner 5 minutes before auto-stop: "Stops at 5:30 PM, next booking waiting".
- "Stop charging" with a confirm sheet.
- When the session ends, swap to a summary card (energy, duration, rate, total) with
  a "Pay ₹X" button placeholder (payment arrives in Phase 6) and a link to Bookings.
- States: loading skeleton, "Session not found", reconnecting banner.

2. CHARGING TAB
- The Charging tab becomes live: a pulsing dot when the user has an ACTIVE session,
  opening that session; otherwise an EmptyState ("No charging right now").
- A small persistent "Charging · 68%" pill in the app bar while a session runs.

3. LIVE UPDATES ELSEWHERE
- Explore pins and the station availability grid update on realtime nudges
  (re-fetch from the API, never trust the message body), with a brief, subtle pulse
  on what changed (disabled under prefers-reduced-motion).
- Use the "Reconnecting…" banner when realtime drops and polling takes over.

4. CHARGER BUSY HANDLING
- If a booking is moved to another charger, update the Ticket and Bookings card
  with a highlighted notice "Moved to CCS2-2, same time" and a toast when the app is open.
- If it is cancelled because no charger was free: "Cancelled, ₹199 refunded" plus
  three nearby alternatives from GET /recommendations.

QUALITY
- Use the admin simulator (external start, unplug) to trigger each state and check
  the UI reacts within a few seconds.
- Check at 375, 768 and 1280 px. npm run build and npm run lint pass.
  No new dependency without asking.

When finished: list the screens and a manual test script using the simulator. Then STOP.
```

---

## Prompt 6-UI: Kiosk app, bill payment, receipts

**Run with:** Phase 6 prompt. **Owner:** D (kiosk), C (payments UI). **Effort:** 4–5 person-days.

```text
We are building ChargeSpot. Read docs/ui-flow.md (sections 1, 6 and 7) and
docs/architecture.md sections 7.3, 8 and 9. The Phase 6 API (device auth, kiosk
status, OTP start, walk-ins with payment links, session bill payment) must exist.
If missing, stop and tell me.

Build the UI for PHASE 6 ONLY.

A. KIOSK APP (frontend/kiosk, new Vite + React + TypeScript + Tailwind v4 workspace)
- Reuse the design tokens from frontend/shared/src/styles/tokens.css and formatting
  from @chargespot/shared. Kiosk scale: base text 20 px, headings 40 px+, touch
  targets ≥ 64 px, maximum contrast, no glass, no hover-only behaviour. Target a
  1280×800 landscape tablet; it must also work at 1024×768.
- Device setup screen (first run): paste the kiosk key, validate with the API,
  store it; a hidden long-press on the logo returns here.
- Status board (home): station name and clock (IST); one large tile per charger
  showing number, plug (ConnectorIcon), kW, price, state (Free / Reserved for 5:00 PM /
  Charging with progress bar / Out of service) and "free until 6:30 PM". Two big
  actions: "Booked? Enter your code" and "No booking? Charge here". No personal data.
- OTP pad: six large digit boxes, on-screen number pad, delete, clear; on success a
  full-screen "Go to Charger ②, plug in" (auto-returns after 8 s); on failure "Wrong
  code, 3 tries left"; cooldown screen "Too many tries. Please wait 1:42".
- Walk-in: choose a free charger → choose ₹100 / ₹200 / ₹500 / "Until 6:25 PM"
  (each with a kWh estimate) → QR (qrcode.react, approved) with a 3:00 countdown and
  "Scan with any UPI app" → "Payment received ✓ Plug in at Charger ③" → tile shows
  "Done · used ₹186 · ₹14 refunded" for 2 minutes. Handle QR expiry and payment failure.
- Idle: after 30 s with no touch, return to the board; after 2 min, a gentle
  attract loop of the two actions. Connection-lost overlay with automatic retry.

B. USER WEB APP: BILLS AND RECEIPTS
- Session summary: the "Pay ₹223.20" button opens Razorpay Checkout; handle success,
  failure and dismissal.
- Bookings → "Payment due" tab lists unpaid sessions with Pay buttons; the dues
  banner on Explore links here.
- Receipt page (/receipts/:sessionId): ticket style; station, charger, start/end
  times, kWh, rate, total, payment ID, "Paid ✓"; a Print/Save as PDF button using the
  browser's print with a print stylesheet (no dependency).

QUALITY
- Kiosk: check on a real tablet or in browser device mode at 1280×800; full flows
  with a test OTP and a test walk-in payment.
- npm run build and npm run lint pass for both apps. No dependency other than
  qrcode.react without asking.

When finished: list the screens, the kiosk setup steps for a real tablet (fullscreen,
keep awake), and a manual test script. Then STOP.
```

---

## Prompt 7-UI: Admin pages and final polish

**Run with:** Phase 7 prompt. **Owner:** D (with everyone for the audit). **Effort:** 3–4 person-days.

```text
We are building ChargeSpot. Read docs/ui-flow.md (sections 5, 6 and 7) and
docs/phases.md Phase 7. The admin API must exist. If missing, stop and tell me.
Use src/components/ui; add any missing table/form components there.

Build the UI for PHASE 7 ONLY.

A. ADMIN (/admin, visible and reachable only for role ADMIN; the server still checks)
- Layout: left sidebar on desktop (Overview, Stations, Bookings, Kiosks, Simulator,
  Alerts), top tabs on phone. Plain, data-dense, no glass.
- Overview: stat tiles (today's bookings, active sessions, no-shows this week,
  revenue split into booking fees / energy / walk-ins) and two simple charts
  (bookings per day, no-shows per station). Build charts with plain SVG/CSS; ask me
  before adding a chart library.
- Stations: searchable, sortable, paginated table (name, operator, source badge,
  chargers, status); edit form (validated); charger list with add/edit; "Set out of
  service" opens a dialog listing affected future bookings and offering "Cancel them
  with full refund".
- Bookings: filters (station, status, date), table, and a history timeline per
  booking from booking_events.
- Kiosks: list with last seen; "Create key" shows the key ONCE in a dialog with copy
  button and warning; Revoke with confirm.
- Simulator: pick station and charger, big buttons (External start, Stop, Fault,
  Recover, Unplug), and a live event log.
- Alerts: kiosk code-guessing, failed webhooks; mark as seen.

B. FINAL POLISH (whole app)
- Global error boundary page ("Something went wrong" + Reload + Go home), 404 page,
  session-expired flow (redirect to sign in, then back to the page), offline banner.
- Consistency audit: every screen uses tokens and components (no stray colours,
  radii or font sizes), the same empty/loading/error patterns, the same wording.
- Accessibility audit: keyboard-only through every main flow, focus order, contrast,
  screen-reader labels, reduced motion. Fix what you find.
- Responsive audit at 375, 768, 1024 and 1280 px for every screen.
- Remove dev-only leftovers except /dev/ui (dev builds only).

QUALITY
- npm run build and npm run lint pass with no warnings you introduced.
- Provide before/after notes for anything the audits changed.

When finished: list the admin screens, the audit findings and fixes, and a final
manual test checklist for the jury demo. Then STOP.
```
