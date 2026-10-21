import React, { useMemo } from 'react';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { useRealtimeRefresh } from '../../lib/useRealtimeRefresh';
import { ActiveSessionContext } from './activeSessionContext';
import type { ActiveSessionState } from './activeSessionContext';
import type { LiveSession } from './types';

const POLL_MS = 20_000;

/**
 * Keeps track of whether the signed-in driver is charging right now, so the app bar can show
 * "Charging · 68%" and the Charging tab can pulse, wherever they are in the app.
 * It asks the API every 20 seconds, and straight away when their station reports a change.
 */
export const ActiveSessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const query = useApiQuery('/api/me/sessions/active', (signal) => apiFetch<LiveSession | null>('/api/me/sessions/active', { signal }));
  const stationId = query.data?.station.station_id;
  useRealtimeRefresh(stationId ? [stationId] : [], query.refresh, { alwaysPollMs: POLL_MS });

  const value = useMemo<ActiveSessionState>(
    () => ({ active: query.data ?? null, loading: query.loading, refresh: query.refresh }),
    [query.data, query.loading, query.refresh],
  );
  return <ActiveSessionContext.Provider value={value}>{children}</ActiveSessionContext.Provider>;
};
