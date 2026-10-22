import { useEffect, useState } from 'react';

/** The current moment on the SERVER's clock (the tablet's own clock may be wrong), refreshed every second. */
export function useServerNow(offsetMs: number): Date {
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setTick(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return new Date(tick + offsetMs);
}
