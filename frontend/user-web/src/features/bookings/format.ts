import { formatDateIST, formatTimeIST } from '@chargespot/shared';

/** "4:30 PM" and "5:30 PM" -> "4:30–5:30 PM"; across noon it keeps both: "11:30 AM – 12:30 PM". */
export function formatTimeRange(startIso: string, endIso: string): string {
  const start = formatTimeIST(startIso);
  const end = formatTimeIST(endIso);
  const startPeriod = start.slice(-2);
  return startPeriod === end.slice(-2) ? `${start.slice(0, -3)}–${end}` : `${start} – ${end}`;
}

/** "Sat 12 Oct · 4:30–5:30 PM" (India time). */
export function formatSlot(startIso: string, endIso: string): string {
  return `${formatDateIST(startIso)} · ${formatTimeRange(startIso, endIso)}`;
}

/** 4 minutes 5 seconds -> "4:05" */
export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.ceil(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
