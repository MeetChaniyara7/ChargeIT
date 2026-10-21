import React from 'react';
import { Link } from 'react-router-dom';
import { Card, buttonClasses, SkeletonBlock } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import type { RecommendationResponse } from '../stations/types';
import type { BookingOut } from './types';

const HOW_MANY = 3;

/**
 * Three nearby places to charge instead, from the same recommendation engine as the map. Shown when a booking
 * was cancelled because its charger was occupied and no other was free.
 */
export const NearbyAlternatives: React.FC<{ booking: BookingOut }> = ({ booking }) => {
  const { latitude, longitude } = booking.station;
  const key = `/api/recommendations?${new URLSearchParams([
    ['lat', String(latitude)],
    ['lng', String(longitude)],
    ['connector', booking.charger.connector_type],
    ['duration', '60'],
  ])}`;
  const query = useApiQuery(key, (signal) => apiFetch<RecommendationResponse>(key, { signal }));

  if (query.loading) {
    return (
      <div role="status">
        <span className="sr-only">Finding other chargers nearby…</span>
        <SkeletonBlock className="h-28" />
      </div>
    );
  }
  // Prefer other stations (this one had nothing free); fall back to it if it is all there is.
  const all = query.data?.results ?? [];
  const others = all.filter((r) => r.station.station_id !== booking.station.station_id);
  const results = (others.length >= HOW_MANY ? others : [...others, ...all.filter((r) => !others.includes(r))]).slice(0, HOW_MANY);
  if (query.error || results.length === 0) {
    return <p className="text-sm text-muted">We could not find another free charger nearby right now. Try the map.</p>;
  }
  return (
    <section aria-labelledby="alternatives-heading" className="space-y-2">
      <h2 id="alternatives-heading" className="text-base font-bold">
        Charge nearby instead
      </h2>
      <ul className="space-y-2">
        {results.map((result) => (
          <li key={result.station.station_id}>
            <Card className="flex items-center justify-between gap-3 p-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold">{result.station.name}</p>
                <p className="text-xs text-muted">{result.reason}</p>
              </div>
              <Link to={`/stations/${result.station.station_id}`} className={buttonClasses({ size: 'sm', variant: 'secondary' })}>
                See chargers
              </Link>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
};
