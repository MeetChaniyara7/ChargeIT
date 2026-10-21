import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { useRealtimeRefresh } from '../../lib/useRealtimeRefresh';
import type { LiveSession } from './types';

/** A live session, plus the moment (on this device's stopwatch) the answer arrived, for the countdown. */
export interface SessionWithClock {
  session: LiveSession;
  receivedAt: number;
}

/** Values are re-asked this often even while live updates work, in case a nudge is missed. */
export const SESSION_POLL_MS = 15_000;

/**
 * One charging session with its live numbers. It refreshes when the station changes (a live nudge),
 * and every 15 seconds as a fallback. The numbers always come from the API.
 */
export function useLiveSession(sessionId: string | undefined) {
  const key = sessionId ? `/api/me/sessions/${encodeURIComponent(sessionId)}` : null;
  const query = useApiQuery(key, async (signal): Promise<SessionWithClock> => {
    const session = await apiFetch<LiveSession>(key as string, { signal });
    return { session, receivedAt: performance.now() };
  });
  const stationId = query.data?.session.station.station_id;
  const { live } = useRealtimeRefresh(stationId ? [stationId] : [], query.refresh, { alwaysPollMs: SESSION_POLL_MS });
  return { ...query, live };
}
