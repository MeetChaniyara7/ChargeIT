import { useEffect } from 'react';

interface WakeLockSentinelLike {
  release: () => Promise<void>;
}

/** Keeps the tablet's screen on while the kiosk is open, where the browser supports it (no dependency). */
export function useWakeLock(enabled: boolean): void {
  useEffect(() => {
    if (!enabled || !('wakeLock' in navigator)) return;
    let sentinel: WakeLockSentinelLike | null = null;
    let cancelled = false;
    const lock = async () => {
      try {
        const next = await (navigator as Navigator & { wakeLock: { request: (type: 'screen') => Promise<WakeLockSentinelLike> } }).wakeLock.request('screen');
        if (cancelled) void next.release();
        else sentinel = next;
      } catch {
        /* refused (battery saver, no permission): the tablet's own screen settings still apply */
      }
    };
    void lock();
    // The browser drops the lock when the page is hidden; take it again when the page is back.
    const onVisible = () => {
      if (document.visibilityState === 'visible') void lock();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
      void sentinel?.release();
    };
  }, [enabled]);
}
