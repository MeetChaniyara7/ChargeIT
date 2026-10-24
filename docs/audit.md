# Final polish audit (Phase 7)

Run on 2026-10-22 in real Chrome (headless) against the running app and the live data, at **375, 768, 1024 and 1280 px**, on 21 pages: the landing page, Explore, a station page, Bookings, Payment due, Charging, Profile, Vehicles, the 404 page and the eleven admin pages (the admin pages were re-checked after the admin got its own screen: Users, Operators, Payments and Activity log were added). The checks are a small script (not in the repository: it uses only Chrome's DevTools protocol, so no dependency was added) that reports:

- buttons and links with no accessible name, form fields with no label, images with no `alt`;
- not exactly one `h1`, duplicate element ids;
- taps smaller than 44 px (buttons, selects, inputs);
- text with a contrast ratio below 4.5 (3 for large text) against its real, blended background;
- a page that scrolls sideways.

A second script tabbed through the main pages with the keyboard only.

## What it found, and what changed

| Where | Before | After |
|---|---|---|
| Explore | No `h1` on the page | A visually hidden `h1` "Find a charger" |
| Explore | The same station card id appeared twice (the "best for you" copy and the list copy) | Only the list copy has the id (it is the scroll target) |
| Map search box | Input 36 px tall, locate button 36 x 36 | 44 px |
| Station page | "Back" 36 px, "Charge now" 42 px | 44 px |
| Station page | Slot cells 40 px tall | 44 px tall (width stays 32 px: a whole day must fit, drag and arrow keys also work) |
| Station cards | The name button was 24 px tall | Same look, 44 px tap area (padding cancelled by a negative margin) |
| "Approximate" tag (30 places) | A 22 px button | Same look, an invisible ring makes the tap area 44 px or more |
| Admin overview on a phone | The page scrolled sideways (grid children could not shrink) | Grid children shrink; charts and bars fit 375 px |
| Admin on a phone | The new admin header (logo, tag, links, sign out) was wider than 375 px and the page scrolled sideways; sign out was a small icon | Avatar hidden on phones, sign out is a 44 px button, tighter spacing |
| Admin tables | Long station names and emails pushed the amount and action columns off a 1280 px screen | Long text is cut with a tooltip; ids sit under the name instead of in a column of their own |
| Whole app | An unexpected crash showed a blank page | An error page: "Something went wrong", Reload, Go home |
| Whole app | An unknown address was sent to the landing page | A 404 page with links to Explore and home |
| Whole app | Offline: nothing said so | A notice while the device is offline, gone when it is back |
| Expired login | Silently sent to Sign in | Sign in explains "Your session ended" and returns to the page afterwards |
| Booking-fee Pay button | A very fast double tap could start two payments | A second tap is ignored while one is open (the server also returns the same order) |

After the fixes the script reports **0 findings at all four widths**, with the exceptions below.

## Exceptions (marked in the code with `data-hit`, or exempt by design)

- **The "Approximate" tag** is small on purpose; its tap area is larger than it looks.
- **The slot grid** cells are 44 px tall but only 32 px wide on a phone: a day has 48 slots. Arrow keys move between cells and Enter or Space picks one.
- **Map pins** (Leaflet markers) are exempt from the size check: every station on the map is also in the list with full-size controls.

## Keyboard-only

On Admin stations, Admin kiosks, Bookings and Profile every Tab stop shows a visible focus ring, the order follows the page (skip link, logo, main menu, the page's own menu, then the content), a dialog keeps focus inside while it is open, Esc closes it and focus returns to the button that opened it.

## Reduced motion

`frontend/shared/src/styles/tokens.css` switches off animations and transitions for people who ask for reduced motion; the new admin screens use no animation of their own.

## Colours, radii and fonts

Every new screen uses the design tokens and the component library. The only literal colours in the new code are the black-on-white of the QR code in the kiosk (a QR code must scan), `text-white` on the red danger button and `text-black` on the amber warning bar (the same pairs the existing buttons use, chosen for contrast), and the browser's own `Canvas` / `CanvasText` in the receipt print rules.

## Still to do by hand

- A pass on a real phone and a real tablet (the audit used Chrome's device emulation).
- A screen-reader pass (NVDA or VoiceOver) through book, pay, charge: the names and labels are in place, but only a person can judge how it sounds.
