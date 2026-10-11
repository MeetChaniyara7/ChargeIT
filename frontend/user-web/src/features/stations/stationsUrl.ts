import { FAST_KW, STATION_LIMIT } from './constants';
import type { ExploreFilters } from './useExploreFilters';
import type { LatLng, MapBounds } from './types';

const round = (n: number) => Math.round(n * 1000) / 1000; // about 100 m: tiny map movements don't re-fetch

type StationFilters = Omit<ExploreFilters, 'query'>;

/** The /api/stations request for a map area, a reference point and the filters. */
export function stationsUrl(bounds: MapBounds, reference: LatLng, filters: StationFilters): string {
  const params = new URLSearchParams({
    bbox: [bounds.west, bounds.south, bounds.east, bounds.north].map(round).join(','),
    lat: String(round(reference.lat)),
    lng: String(round(reference.lng)),
    limit: String(STATION_LIMIT),
  });
  filters.connectors.forEach((c) => params.append('connector', c));
  const minKw = Math.max(filters.fast ? FAST_KW : 0, filters.minKw ?? 0);
  if (minKw > 0) params.set('min_power_kw', String(minKw));
  if (filters.maxPrice !== null) params.set('max_price', String(filters.maxPrice));
  if (filters.operator) params.set('operator', filters.operator);
  if (filters.openNow) params.set('open_now', 'true');
  return `/api/stations?${params}`;
}
