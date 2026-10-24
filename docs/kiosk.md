# The station kiosk

One tablet per station, shared by everyone standing there, like an ATM. It shows the chargers, starts charging with a code from the app, or sells a walk-in session for a UPI payment. It never shows a name, a phone number or an app user's bill. App users stop charging and pay in the web app.

Code: `frontend/kiosk/` (the app), `backend/app/features/kiosk/` (the API). The design rules are in `docs/architecture.md` sections 7.3 and 9, what is built in section 18, the flows in `docs/FLOW.md`.

## Screens

| Screen | What it does |
|---|---|
| **Setup** (first run) | Paste the kiosk key; the server checks it before it is saved on the tablet. Later, the **Change station** button (the gear in the header) or a long press (3 seconds) on the ChargeSpot logo opens it again: it shows which station the tablet is set up for, keeps that station until a valid new key is pasted, has a Cancel button, and closes itself after 60 seconds without a touch. A key the server later refuses is forgotten and this screen explains why. |
| **Status board** (home) | A tile per charger: number, plug, kW, price per kWh, state (Free, Reserved, Charging with a progress bar, Being taken, Out of service), "free until 6:30 PM", "Reserved for 5:00 PM", "Walk-in · ₹120 of ₹200 used". A walk-in that just finished shows "Done · used ₹186 · ₹14 refunded" for 2 minutes. Station name and the India-time clock (from the server's clock) are in the header. Two big buttons: "Booked? Enter your code" and "No booking? Charge here". After 2 minutes without a touch the two buttons take turns glowing. |
| **Enter your code** | Six boxes and a number pad (digits, Clear, delete). The 6th digit sends the code. "Wrong code, 3 tries left"; "Too many tries. Please wait 1:42"; a clear message when the code is not valid yet or any more. |
| **Code accepted / Payment received** | Full screen: "Go to Charger CCS2-1 and plug in", with the plug type. Returns to the board after 8 seconds, or on "Done". |
| **Which charger?** | The free chargers that can take a walk-in. If none: the reason for each charger. |
| **How much?** | ₹100, ₹200, ₹500 and "Until 6:25 PM" (the whole window, priced by the server), each with the kWh it buys. |
| **Scan to pay** | A QR code (black on white, 340 px) for the Razorpay payment link, the amount, a 3:00 countdown, "Waiting for your payment…" and Cancel. When the payment arrives the screen changes by itself. |
| **QR ran out / cancelled** | "The payment code ran out", with "if money was taken it is refunded automatically", or "Your payment came too late, ₹X will be refunded in full". Start again or back to the board. |
| **Connection lost** | A full-screen cover while the server cannot be reached (after 2 failed polls). It keeps trying and goes away by itself. The board underneath keeps the last answer. |

Every screen except the QR code goes back to the board after 30 seconds without a touch. The QR screen ends by itself (paid, 3 minutes, or Cancel).

Sizes: the root font is 20 px (base text 20 px, headings 40 px and up), buttons are at least 80 px tall, no hover-only behaviour, dark theme from `tokens.css`. Checked at 1280 × 800 and 1024 × 768 (the layout switches at 1200 px).

## Stopping a walk-in early

A walk-in has no account, so it cannot be tracked or stopped from the app. After paying, the kiosk shows a 6-digit **stop code** once (25 seconds). Pressing **Stop & refund** on the board and typing it ends the charging: the energy used is billed and the unused part of the prepaid amount is recorded as a refund. The code only works at the same station, once, and wrong tries count towards the normal cooldown and alert. A lost code: an admin can stop the session from Admin, Simulator, Unplug.

## Setting up a real tablet

1. **Make a key** for the station (repo root, backend venv active):
   `cd backend` then `python -m scripts.make_kiosk_key "<part of the station name>" --name "Entrance kiosk"`.
   Copy the key it prints: it is shown once and only a hash is stored. (Admins can also call `POST /api/admin/stations/{id}/devices`.)
2. **Allow the kiosk's address** in `backend/.env`: add it to `CORS_ORIGINS` (for example `http://localhost:5174` while developing).
3. **Run the kiosk**: in `frontend/kiosk` copy `.env.example` to `.env` (set `VITE_API_URL`), then `npm run dev:kiosk` from the repo root (port 5174), or `npm run build` and serve `frontend/kiosk/dist`.
4. **On the tablet** open the kiosk address in Chrome, paste the key on the setup screen and press "Connect this kiosk". The station name appears when it works.
5. **Full screen**: press "Full screen" on the setup screen, or install the page to the home screen (Chrome menu, "Add to Home screen"), or start Chrome with `--kiosk <address>` (Windows or Linux tablet). On Android, pin the app (Settings, Security, App pinning) so nobody leaves it.
6. **Keep awake**: the kiosk asks the browser to keep the screen on. Also set the tablet's screen timeout to the longest value (or "never" while charging) and keep it plugged in. Turn off auto-rotate and lock the landscape orientation.
7. **A lost or replaced tablet**: switch its key off with `POST /api/admin/devices/{id}/disable` (the key stops working at once) and make a new one.

## Manual test script

Needs the API running, the kiosk running and a demo account with no unpaid bill. Use a station whose chargers are free.

1. **Setup**: open the kiosk with an empty browser profile. Paste a wrong key: "That key is not valid". Paste the right key: "Connected to <station>", then the board appears.
2. **Board**: the chargers show with price and power. The clock matches India time. No name or bill appears anywhere. Unplug the network cable (or block the API): "Connection lost" appears within about 10 seconds; restore it: the cover disappears by itself.
3. **Booked journey**: in the web app press "Charge now" on a free charger (or book and pay the ₹199 fee), and keep the code. At the kiosk press "Booked? Enter your code", type a wrong code ("Wrong code, 4 tries left"), then the right one: "Go to Charger X and plug in", then the board shows that charger "Charging" with a progress bar. On the phone the charging page shows the same charger live.
4. **Code rules**: type 5 wrong codes: "Too many tries. Please wait 2:00" counting down, the pad is disabled. A used code does not work a second time. A code from another station does not work.
5. **Stop and pay**: on the phone press "Stop charging" (or `python -m scripts.simulate event UNPLUG "<station>" <label>`). The summary shows "Pay ₹X". Press it, pay with the Razorpay test card, and see "Paid. Thank you!" and "View receipt". The Payment due tab is empty and the Explore banner is gone. Open the receipt and use "Print / save as PDF": only the receipt is printed.
6. **Walk-in journey**: at the kiosk press "No booking? Charge here", pick a charger, pick ₹100: a QR with a 3:00 countdown. Scan it with a phone and pay in test mode (Razorpay test UPI `success@razorpay`, or any test card on the hosted page). Within a few seconds the kiosk says "Payment received ✓, go to Charger X". The board shows "Walk-in · ₹… of ₹100 used". Unplug it (`simulate event UNPLUG`): the tile shows "Done · used ₹… · ₹… refunded" for 2 minutes.
7. **Walk-in rules**: while the QR is up, the same charger shows "Being taken" and cannot be booked in the app. Press Cancel: it is free again at once. Let a QR run out: "The payment code ran out", and the charger is free. Book the charger for 20 minutes from now and start a walk-in: the window ends 5 minutes before that booking.
8. **Idle**: open the code pad and do not touch it: it returns to the board after 30 seconds. Leave the board for 2 minutes: the two buttons take turns glowing.
