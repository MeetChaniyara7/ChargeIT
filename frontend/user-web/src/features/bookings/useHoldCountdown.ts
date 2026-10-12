import { useEffect, useState } from 'react';
import { PAYMENT_HOLD_SECONDS } from '@chargespot/shared';
import type { BookingWithClock } from './useBookings';

/**
 * Seconds left on a hold, counted from the SERVER's numbers: (hold_expires_at - server_time) at the
 * moment the answer arrived, minus the time this device's stopwatch has run since. A phone with the
 * wrong clock still shows the right countdown, and the page asks the server again when it reaches zero.
 */
export function useHoldCountdown(data: BookingWithClock | undefined) {
  const [now, setNow] = useState(() => performance.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(performance.now()), 250);
    return () => window.clearInterval(timer);
  }, []);

  const hold = data?.booking.hold_expires_at;
  if (!data || !hold) return { secondsLeft: null as number | null, fraction: 0 };
  const total = (new Date(hold).getTime() - new Date(data.booking.server_time).getTime()) / 1000;
  const secondsLeft = Math.max(0, total - (now - data.receivedAt) / 1000);
  return { secondsLeft, fraction: Math.min(1, secondsLeft / PAYMENT_HOLD_SECONDS) };
}
