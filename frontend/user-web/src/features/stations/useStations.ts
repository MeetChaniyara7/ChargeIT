import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { MAP_SETTLE_MS } from './constants';
import { stationsUrl } from './stationsUrl';
import type { ExploreFilters } from './useExploreFilters';
import type { LatLng, MapBounds, StationSearchResponse } from './types';

/**
 * The stations in the part of the map that is showing, with the active filters.
 * Waits until the map has stood still for a moment, so panning doesn't send a request per frame.
 *
 * `reference` is the point distances are measured from (the user, or the map centre).
 * The previous results stay on screen while new ones load.
 */
export function useStations(bounds: MapBounds | null, reference: LatLng | null, filters: ExploreFilters) {
  const settledBounds = useDebouncedValue(bounds, MAP_SETTLE_MS);
  // The URL is a plain string, so it only changes when the request really changes.
  const key = settledBounds && reference ? stationsUrl(settledBounds, reference, filters) : null;

  const query = useApiQuery(key, (signal) => apiFetch<StationSearchResponse>(key as string, { signal }));
  return {
    stations: query.data?.stations ?? [],
    truncated: query.data?.truncated ?? false,
    loading: query.loading || (key === null && bounds === null),
    refreshing: query.refreshing,
    error: query.error,
    retry: query.retry,
    /** The map area the current results are for (used by the "no results" helper). */
    settledBounds,
  };
}
