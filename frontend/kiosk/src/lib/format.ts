// Small display helpers for the kiosk. Pure, so they have unit tests.

import { formatINR } from '@chargespot/shared';

/** 186 -> "₹186"; 186.5 -> "₹186.50". Whole rupees are shown without ".00" because the kiosk shows round amounts. */
export function rupees(amount: number): string {
  return Number.isInteger(amount) ? formatINR(amount).replace(/\.00$/, '') : formatINR(amount);
}

/** 102 -> "1:42"; negative numbers count as 0. */
export function clockMinutes(totalSeconds: number): string {
  const s = Math.max(0, Math.ceil(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** 12.34 -> "12.3 kWh" (one decimal: it is an estimate). */
export function kwhText(kwh: number): string {
  return `${kwh.toFixed(1)} kWh`;
}

/**
 * The tablet's own clock can be wrong, so times shown on the board follow the server's clock:
 * `offsetMs` is (server time - this device's time) when the last answer arrived.
 */
export function clockOffsetMs(serverTime: string, deviceNowMs: number): number {
  return Date.parse(serverTime) - deviceNowMs;
}
