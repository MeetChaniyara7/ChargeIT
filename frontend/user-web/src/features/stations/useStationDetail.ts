import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import type { StationAvailability, StationDetail } from './types';

/** One station with its chargers. */
export function useStationDetail(stationId: string | undefined) {
  const key = stationId ? `/api/stations/${encodeURIComponent(stationId)}` : null;
  return useApiQuery(key, (signal) => apiFetch<StationDetail>(key as string, { signal }));
}

/** The 30-minute blocks for one station on one IST day ("YYYY-MM-DD"). */
export function useAvailability(stationId: string | undefined, date: string) {
  const key = stationId ? `/api/stations/${encodeURIComponent(stationId)}/availability?date=${date}` : null;
  return useApiQuery(key, (signal) => apiFetch<StationAvailability>(key as string, { signal }));
}
