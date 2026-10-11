// Display helpers. Times are stored in UTC and always shown in India time (IST).

import { DISPLAY_TIME_ZONE } from './constants';

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 223.2 -> "₹223.20" */
export function formatINR(amount: number): string {
  return inrFormatter.format(amount);
}

/** A UTC timestamp shown in IST, e.g. "10 Oct 2026, 4:30 pm". Pass options to change the format. */
export function formatIST(value: Date | string, options: Intl.DateTimeFormatOptions = {}): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: DISPLAY_TIME_ZONE,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    ...options,
  }).format(date);
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** The IST calendar date of an instant as "YYYY-MM-DD" (en-CA formats dates that way). */
function istDateKey(date: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: DISPLAY_TIME_ZONE }).format(date);
}

/** "4:30 PM" (always upper-case AM/PM, always IST). */
export function formatTimeIST(value: Date | string): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: DISPLAY_TIME_ZONE,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
    .format(date)
    .replace(/\b(am|pm)\b/i, (m) => m.toUpperCase());
}

/** "Sun 13 Oct" (IST). Adds the year when it is not the current year. */
export function formatDateIST(value: Date | string, now: Date = new Date()): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  const parts = new Intl.DateTimeFormat('en-IN', {
    timeZone: DISPLAY_TIME_ZONE,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  const base = `${get('weekday')} ${get('day')} ${get('month')}`;
  return get('year') === new Intl.DateTimeFormat('en-IN', { timeZone: DISPLAY_TIME_ZONE, year: 'numeric' }).format(now)
    ? base
    : `${base} ${get('year')}`;
}

/**
 * Friendly IST date and time for people:
 *   "Today, 4:30 PM" · "Tomorrow, 9:00 AM" · "Sun 13 Oct, 4:30 PM"
 * Pass `withTime: false` for just "Today" / "Tomorrow" / "Sun 13 Oct". `now` exists for tests.
 */
export function formatRelativeIST(value: Date | string, options: { withTime?: boolean; now?: Date } = {}): string {
  const { withTime = true, now = new Date() } = options;
  const date = typeof value === 'string' ? new Date(value) : value;
  const key = istDateKey(date);
  // India has no daylight saving, so "tomorrow" is exactly 24 hours after now.
  const day =
    key === istDateKey(now) ? 'Today' : key === istDateKey(new Date(now.getTime() + DAY_MS)) ? 'Tomorrow' : formatDateIST(date, now);
  return withTime ? `${day}, ${formatTimeIST(date)}` : day;
}
