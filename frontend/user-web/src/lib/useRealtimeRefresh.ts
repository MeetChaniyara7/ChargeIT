import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { anyChannelDown, realtimeConfigured, subscribeToStatus, subscribeToStation } from './realtime';
import type { RealtimeState } from './realtime';

/** Nudges that arrive together (a job changing many rows) cause one refresh, not many. */
const COALESCE_MS = 300;
/** How often to ask the API when live updates are not working. */
export const FALLBACK_POLL_MS = 30_000;

interface Options {
  /** Ask the API this often even while live updates work (e.g. the charging page uses 15 s). */
  alwaysPollMs?: number;
}

/**
 * Keeps a screen fresh. When something changes at one of `stationIds`, `refresh` is called (the caller
 * re-fetches from the API; the message itself is never trusted). If live updates are unavailable or have
 * dropped, `refresh` is called every 30 seconds instead. It is also called when the tab becomes visible again.
 *
 * Returns whether live updates are working right now.
 */
export function useRealtimeRefresh(stationIds: readonly string[], refresh: () => void, options: Options = {}) {
  const refreshRef = useRef(refresh);
  useEffect(() => {
    refreshRef.current = refresh;
  });

  // Which stations are live. A station that has no state yet counts as connecting, not down.
  const [states, setStates] = useState<Record<string, RealtimeState>>({});
  const key = [...new Set(stationIds)].sort().join(',');

  useEffect(() => {
    const ids = key ? key.split(',') : [];
    let timer: number | undefined;
    const nudge = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => refreshRef.current(), COALESCE_MS);
    };
    const stops = ids.map((id) => subscribeToStation(id, nudge, (state) => setStates((previous) => (previous[id] === state ? previous : { ...previous, [id]: state }))));
    return () => {
      window.clearTimeout(timer);
      stops.forEach((stop) => stop());
    };
  }, [key]);

  const ids = key ? key.split(',') : [];
  const live = realtimeConfigured && ids.every((id) => states[id] !== 'down');

  // Polling: always when asked, otherwise only while live updates are not working.
  const alwaysPollMs = options.alwaysPollMs;
  useEffect(() => {
    if (ids.length === 0 && alwaysPollMs === undefined) return;
    const every = live ? alwaysPollMs : Math.min(alwaysPollMs ?? FALLBACK_POLL_MS, FALLBACK_POLL_MS);
    if (every === undefined) return;
    const timer = window.setInterval(() => refreshRef.current(), every);
    return () => window.clearInterval(timer);
    // `ids` is derived from `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, alwaysPollMs, key]);

  // Coming back to the tab (or the phone waking up) refreshes straight away.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') refreshRef.current();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  return { live };
}

/** True while a live connection has dropped and polling has taken over (drives the Reconnecting banner). */
export function useRealtimeDown(): boolean {
  return useSyncExternalStore(subscribeToStatus, anyChannelDown, () => false);
}
