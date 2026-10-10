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
