# ChargeSpot: UI Direction and Screen Flow

The agreed look, feel and screen flow for every ChargeSpot screen. The prompts that build it are in [ui-prompts.md](ui-prompts.md). Backend behaviour lives in [architecture.md](architecture.md).

---

## 1. Design direction: "Midnight Charge"

**Goal:** a calm, premium, purpose-built EV app, not a generic "AI template" dashboard.

| Principle | Rule |
|---|---|
| **Base style** | Material-style "flat 2.0": solid dark surfaces, 3 elevation levels (page → card → popover/sheet), subtle shadows. |
| **Glass** | **Only over the map** (search bar, filter chips, map controls, bottom sheet), where seeing the map underneath helps. Nowhere else. |
| **Never** | Aurora/gradient-mesh blobs, gradient text, glowing borders everywhere, animated conic borders, emoji as icons, neumorphism, marketing filler copy ("Next-Gen Platform"). |
| **Colour with a job** | Green = available and primary actions · amber = few left, warnings, timers · rose = busy, errors, destructive · sky = info, your location. One meaning per colour, everywhere. |
| **One glow at most** | Only on the live charging ring. |
| **Mobile first** | Design for 375 px wide first, then widen. Most drivers book from a phone. |
| **EV-specific details** | Connector plug icons, the seat-map slot grid, the movie-ticket booking card, the battery ring. These make it look like a real EV product. |
| **Real content** | "42 stations near you · 18 free now", not slogans. |
| **Honest data** | An "Approximate" tag (dotted outline + tooltip) on synthetic or estimated values. Never invent numbers on screen. |

### Colour tokens

| Token | Value | Use |
|---|---|---|
| `bg` | `#0B1120` | page background |
| `surface` | `#111A2E` | cards, navbar, sheets |
| `surface-raised` | `#18233B` | hover, inputs, chips, popovers |
| `border` | `#24314D` | dividers, outlines |
| `text` | `#E6EDF7` | main text |
| `text-muted` | `#94A3B8` | secondary text |
| `primary` | `#22C55E` | brand, primary buttons, "available", selection |
| `primary-strong` | `#16A34A` | primary hover/pressed |
| `info` | `#38BDF8` | your location, links, info |
| `warning` | `#F59E0B` | few left, hold timer, end-of-slot warning |
| `danger` | `#F43F5E` | busy, errors, cancel (text on page/cards, map pins) |
| `danger-strong` | `#E11D48` | red **backgrounds**, i.e. the danger button (white on `#F43F5E` is only 3.7:1) |
| `danger-soft` | `#FB7185` | red **text on a tinted red background** (badges, error alerts; plain `danger` is only 4.1:1 there) |
| `field-border` | `#55688F` | outlines of inputs and chips (WCAG needs 3:1 for UI boundaries; `border` is only a soft divider) |
| `on-primary` | `#052E16` | text on green buttons (white on `#22C55E` is only 2.2:1) |

All colours are CSS variables (Tailwind v4 `@theme`), so a light theme can be added later without touching components. The tokens live in `frontend/shared/src/styles/tokens.css` and every text/background pair was checked against WCAG AA (4.5:1 text, 3:1 borders).

### Type, shape, motion
- **Font:** Plus Jakarta Sans (Google Fonts). **Tabular (fixed-width) numbers** for prices, kWh, times and OTP digits.
- **Type scale:** 12 · 14 · 16 · 20 · 28 px (+ 36 px for the OTP and battery %). Two weights: 500 and 700.
- **Spacing:** 4 px grid. **Radius:** 8 px for controls, 12 px for cards, 16 px for sheets.
- **Motion:** 150–250 ms ease-out; respects `prefers-reduced-motion`.
- **Accessibility:** WCAG AA contrast, visible keyboard focus ring, labels on icon-only buttons, status shown with **text + colour**, tap targets ≥ 44 px.

---

## 2. Screen map (driver web app)

```
Public                          Signed in: bottom tabs on phone, top bar on desktop
──────                          ───────────────────────────────────────────────────
/            Landing            [Explore]   /explore              map + station list
/login       Sign in                        /stations/:id         station + slot grid
/register    Sign up                        /book/:bookingId      hold timer + payment
                                            /tickets/:bookingId   confirmation + OTP
                                [Bookings]  /bookings             Upcoming · Past · Payment due
                                [Charging]  /charging/:sessionId  live battery ring
                                [Profile]   /profile              details, vehicles, sign out
                                            /profile/vehicles
                                (admins)    /admin/...            see section 6
```
`/dashboard` (old) redirects to `/explore`. Signed-in users visiting `/` go to `/explore`. After signing in, users return to the page they were heading to (e.g. `/explore?q=bopal` from the landing search). `/dev/ui` (development builds only) is the component style guide.

---

## 3. Main journey

```
Landing → Sign in → Explore → Station → Pick slots → Hold & pay → Ticket (OTP)
                                                                      │
              Bookings ← Kiosk: enter OTP → Live charging → Summary → Pay bill → Receipt
```

### Explore (`/explore`)
```
┌──────────────────────────────┐
│ [🔍 Search place or station ]│  glass bar over the map
│ (CCS2) (Fast 50kW+) (Open now)│  filter chips
│        (2)   (1)    (0)       │  pins show free chargers, coloured by availability
│    ● you                      │
├───────────── ═══ ─────────────┤  draggable bottom sheet (peek / half / full)
│ ★ Best for you now            │
│ Tata Power – Riya Autolink    │
│ 2 CCS2 free · 1.2 km · ₹18    │
│ MobiLane AMC Prahladnagar …   │
└──────────────────────────────┘
```
Desktop: list panel on the left (400 px), map on the right.

### Station page (`/stations/:id`)
```
Tata Power – Riya Autolink      ★4.7  1.2 km · 6 min
Bopal-Ambli Road · Open 24/7     [Navigate] [Share]
Chargers  [CCS2 30 kW ₹18] [CHAdeMO 25 kW ₹19.50]  (Approximate)
 Today | Sun 13 | Mon 14 | …
          4:00  4:30  5:00  5:30  6:00
 CCS2-1   [  ]  [██]  [██]  [  ]  [▒▒]      ██ selected   ▒▒ booked
 CHAdeMO  [▒▒]  [  ]  [  ]  [  ]  [  ]
┃ CCS2-1 · 4:30–5:30 PM · Booking fee ₹199 · est. ₹486   [Hold & pay →] ┃  sticky bar
```

### Hold & pay (`/book/:id`)
Countdown ring "Slot held for you · 4:32", summary, **Pay ₹199** (Razorpay), Cancel releases the hold.

### Ticket (`/tickets/:id`)
Movie-ticket card: station, date and time, charger, tear line, **OTP in six digit tiles**, "Valid from 4:15 PM", Navigate, Add to calendar. Shown once; "Show new code" in Bookings.

### Live charging (`/charging/:id`)
Battery ring (%), kWh, cost so far, time left, amber warning 5 min before auto-stop, Stop button. Then a summary card → **Pay ₹X** → receipt.

---

## 4. Other flows

| Flow | Path |
|---|---|
| Charge now | Station → "Charge now" on a free charger → Ticket → kiosk → Live charging |
| Cancel | Bookings → booking → Cancel → sheet "You'll get ₹149.25 back" → Confirm → toast |
| Lost code | Bookings → booking → Show new code (old one stops working) |
| Pending bill | Bookings → Payment due → Pay; banner on Explore "Clear ₹223 to book again" |
| Vehicles | Profile → Vehicles → add (model, plug, battery); pre-fills the connector filter |

## 5. When things go wrong

| Situation | What the user sees |
|---|---|
| Slot just taken | Sheet: "Just taken. Here are 3 alternatives" with one-tap booking |
| Hold expired | Ring hits 0:00 → "Hold expired, slot released" → back to the grid, selection kept |
| Payment failed or closed | "Payment didn't go through" → Try again (hold continues) |
| Charger busy at start | Ticket updates: "Moved to CCS2-2, same time", or "Cancelled, ₹199 refunded" plus nearby options |
| No-show | Past tab, grey "No-show" badge, "Fee kept" |
| Unpaid bill | Book buttons disabled with a banner linking to Payment due |
| Offline / server waking | Slim top banner "Reconnecting…"; content stays visible |

---

## 6. Kiosk and admin

**Kiosk** (station tablet, landscape, readable from 2 m):
```
Status board ─► [Booked? Enter your code] ─► number pad ─► "Go to Charger ②, plug in" ─► board
            └─► [No booking? Charge here] ─► charger ─► amount ─► QR + 3:00 ─► "Paid ✓ plug in"
```
Huge tiles per charger (state, progress, free until, price), no personal data, auto-reset after 30 s, wrong-code cooldown message.

**Admin** (`/admin`, admins only): Overview (today's numbers, simple charts) · Stations (list, edit, chargers, out of service) · Bookings (filters, history timeline) · Kiosks (create key shown once, revoke) · Simulator (external start, stop, fault, unplug) · Alerts. Plain, data-dense tables, no glass.

---

## 7. Patterns used everywhere
- **Loading:** skeletons, never a blank page or a lone spinner.
- **Empty states:** small illustration + one action ("No bookings yet → Find a charger").
- **Toasts:** bottom, for confirmations and short errors.
- **Choices:** bottom sheets on phone, dialogs on desktop.
- **Status badges:** colour + word: Free · Few left · Busy · Offline.
- **Formatting:** "Today, 4:30 PM", "Sun 13 Oct"; ₹ with Indian grouping (₹1,23,456.50).

## 8. Build order

| Step | UI delivered |
|---|---|
| UI pass (before Phase 3) | Theme, building blocks, navigation, Landing, Sign in, Profile shell |
| Phase 3 | Explore, Station page (read-only grid) |
| Phase 4 | Interactive slot grid, Hold & pay, Ticket/OTP, Bookings, cancel, Charge now, vehicles |
| Phase 5 | Live charging page, live updates, "charger busy" handling |
| Phase 6 | Kiosk, bill payment, receipts |
| Phase 7 | Admin pages, final error states |
