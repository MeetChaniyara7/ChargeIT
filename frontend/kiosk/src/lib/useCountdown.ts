import { useEffect, useState } from 'react';

/**
 * Whole seconds left, counting down from a number the server gave us. It uses this device's stopwatch
 * (not its clock), so a wrong tablet clock cannot make a QR code look valid after it expired.
 * `resetKey` restarts the count (a new answer arrived).
 */
export function useCountdown(secondsAtReceipt: number | null, resetKey: unknown): number | null {
  const [now, setNow] = useState(() => performance.now());
  const [anchor, setAnchor] = useState<{ key: unknown; at: number }>(() => ({ key: resetKey, at: performance.now() }));
  if (anchor.key !== resetKey) setAnchor({ key: resetKey, at: performance.now() });

  useEffect(() => {
    const timer = window.setInterval(() => setNow(performance.now()), 250);
    return () => window.clearInterval(timer);
  }, []);

  if (secondsAtReceipt === null) return null;
  return Math.max(0, Math.ceil(secondsAtReceipt - (now - anchor.at) / 1000));
}
