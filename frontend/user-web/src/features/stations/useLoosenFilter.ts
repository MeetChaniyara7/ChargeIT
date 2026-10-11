import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { activeFilters, withoutFilter } from './filterLabels';
import type { FilterKey } from './filterLabels';
import { stationsUrl } from './stationsUrl';
import type { ExploreFilters } from './useExploreFilters';
import type { LatLng, MapBounds, StationSearchResponse } from './types';

export interface LoosenSuggestion {
  key: FilterKey;
  label: string;
  /** How many stations would show without this filter. */
  count: number;
}

/**
 * When the filters leave nothing on the map, find the ONE filter whose removal brings
 * back the most stations, so the list can offer "Show without <filter>".
 * Only runs while there are no results (one small request per active filter).
 */
export function useLoosenFilter(
  bounds: MapBounds | null, reference: LatLng | null, filters: ExploreFilters, noResults: boolean,
): LoosenSuggestion | null {
  const active = activeFilters(filters);
  const variants = bounds && reference && noResults
    ? active.map(({ key, label }) => ({ key, label, url: stationsUrl(bounds, reference, { ...filters, ...withoutFilter(key) }) }))
    : [];
  const key = variants.length ? variants.map((v) => v.url).join('|') : null;

  const query = useApiQuery(key, async (signal) => {
    const counts = await Promise.all(variants.map((v) => apiFetch<StationSearchResponse>(v.url, { signal }).then((r) => r.count)));
    const best = variants
      .map((v, i) => ({ key: v.key, label: v.label, count: counts[i] }))
      .sort((a, b) => b.count - a.count)[0];
    return best && best.count > 0 ? best : null;
  });

  return key ? (query.data ?? null) : null;
}
