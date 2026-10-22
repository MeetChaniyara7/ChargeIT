import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, kioskFetch } from './api';
import type { KioskStatus } from './api';
import { clockOffsetMs } from './format';

export const STATUS_POLL_MS = 4_000;
/** The overlay appears after this many failed polls in a row (one dropped request is not an outage). */
const OFFLINE_AFTER_FAILURES = 2;

export interface KioskStatusState {
  status: KioskStatus | null;
  /** True while the server cannot be reached. The board keeps showing the last good answer underneath. */
  offline: boolean;
  /** True when the server says this kiosk's key is not valid (any more). */
  keyRejected: boolean;
  /** Server time minus this device's time, in ms, from the last answer. */
  offsetMs: number;
  /** Ask again now (after a start, a payment...). */
  refresh: () => void;
}

/** The status board's data: asked every 4 seconds, and again on demand. Failures never clear what is on screen. */
export function useKioskStatus(enabled: boolean, key: string | null): KioskStatusState {
  const [status, setStatus] = useState<KioskStatus | null>(null);
  const [failures, setFailures] = useState(0);
  // Remember WHICH key the server refused, so pasting a new key clears the problem without any reset code.
  const [rejectedKey, setRejectedKey] = useState<string | null>(null);
  const [offsetMs, setOffsetMs] = useState(0);
  const [tick, setTick] = useState(0);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled || (key !== null && rejectedKey === key)) return; // a refused key is not asked again
    let stopped = false;
    const ask = async () => {
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;
      try {
        const next = await kioskFetch<KioskStatus>('/api/kiosk/status', { signal: controller.signal });
        if (stopped) return;
        setStatus(next);
        setOffsetMs(clockOffsetMs(next.server_time, Date.now()));
        setFailures(0);
      } catch (error) {
        if (stopped || (error instanceof DOMException && error.name === 'AbortError')) return;
        if (error instanceof ApiError && (error.code === 'INVALID_DEVICE_KEY' || error.code === 'DEVICE_DISABLED')) {
          setRejectedKey(key);
          return;
        }
        setFailures((n) => n + 1);
      }
    };
    void ask();
    const timer = window.setInterval(() => void ask(), STATUS_POLL_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      inFlight.current?.abort();
    };
  }, [enabled, key, rejectedKey, tick]);

  const refresh = useCallback(() => setTick((n) => n + 1), []);
  return { status, offline: failures >= OFFLINE_AFTER_FAILURES, keyRejected: key !== null && rejectedKey === key, offsetMs, refresh };
}
