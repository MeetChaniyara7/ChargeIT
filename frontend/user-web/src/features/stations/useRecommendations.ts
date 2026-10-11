import { useEffect, useState } from 'react';
import { apiFetch } from '../../lib/api';
import { haversineKm } from '../../lib/geo';
import { useApiQuery } from '../../lib/useApiQuery';
import type { LatLng, RecommendationResponse } from './types';

/** Moving the map less than this far does not change the recommendations. */
const MOVE_THRESHOLD_KM = 1;
const SETTLE_MS = 800;
const DURATION_MINUTES = 60;

/**
 * "Best for you now": the top stations for an hour of charging starting now, near `reference`.
 * Re-asked only when the reference point has settled more than 1 km from the last one, or the
 * plug filter changes, not on every small pan of the map.
 */
export function useRecommendations(reference: LatLng | null, connectors: string[]) {
  const [point, setPoint] = useState<LatLng | null>(null);

  useEffect(() => {
    if (!reference) return;
    const timer = window.setTimeout(() => {
      // Keep the old point (no re-render, no new request) unless the new one is really different.
      setPoint((previous) =>
        previous && haversineKm(previous.lat, previous.lng, reference.lat, reference.lng) <= MOVE_THRESHOLD_KM ? previous : reference,
      );
    }, SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [reference]);

  const key = point
    ? `/api/recommendations?${new URLSearchParams([
        ['lat', point.lat.toFixed(4)],
        ['lng', point.lng.toFixed(4)],
        ['duration', String(DURATION_MINUTES)],
        ...connectors.map((c): [string, string] => ['connector', c]),
      ])}`
    : null;

  const query = useApiQuery(key, (signal) => apiFetch<RecommendationResponse>(key as string, { signal }));
  return {
    recommendations: query.data?.results.slice(0, 3) ?? [],
    loading: query.loading,
    // A failure here just hides the section: recommendations are a bonus, not the main job.
    error: query.error,
  };
}
