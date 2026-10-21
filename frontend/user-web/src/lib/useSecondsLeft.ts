import { useEffect, useState } from 'react';

/**
 * A countdown that starts from the server's number: `secondsLeft` as it was when the answer arrived,
 * minus the time this device's own stopwatch has run since (`receivedAt`, from performance.now()).
 * The phone's clock is never read, so a wrong clock cannot make the count wrong.
 */
export function useSecondsLeft(secondsLeft: number | null | undefined, receivedAt: number | undefined): number | null {
  const [now, setNow] = useState(() => performance.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(performance.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  if (secondsLeft == null || receivedAt === undefined) return null;
  return Math.max(0, Math.round(secondsLeft - (now - receivedAt) / 1000));
}

/** 3725 -> "1:02:05", 125 -> "2:05" */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`;
}
