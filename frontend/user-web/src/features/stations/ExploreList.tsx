import React from 'react';
import { AlertCircle, MapPin, RefreshCw } from 'lucide-react';
import { Button, Card, EmptyState, SkeletonBlock } from '../../components/ui';
import { StationCard } from './StationCard';
import type { FilterKey } from './filterLabels';
import type { LocationStatus } from './useGeolocation';
import type { LoosenSuggestion } from './useLoosenFilter';
import type { Recommendation, StationSummary } from './types';

interface ExploreListProps {
  stations: StationSummary[];
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  onRetry: () => void;
  truncated: boolean;
  recommendations: Recommendation[];
  /** True when recommendations are measured from the user, false when from the map centre. */
  recommendationsFromUser: boolean;
  selectedId: string | null;
  onSelect: (stationId: string) => void;
  showDistance: boolean;
  hasFilters: boolean;
  onClearFilters: () => void;
  /** When filters leave nothing, the one filter whose removal brings back the most stations. */
  loosen: LoosenSuggestion | null;
  onLoosen: (key: FilterKey) => void;
  locationStatus: LocationStatus;
  onLocate: () => void;
}

/** "Best for you now" and the stations in the visible map area. Used in the phone sheet and the desktop panel. */
export const ExploreList: React.FC<ExploreListProps> = ({
  stations, loading, refreshing, error, onRetry, truncated, recommendations, recommendationsFromUser, selectedId, onSelect,
  showDistance, hasFilters, onClearFilters, loosen, onLoosen, locationStatus, onLocate,
}) => {
  const locationOff = locationStatus === 'denied' || locationStatus === 'unavailable';

  return (
    <div className="space-y-5">
      {locationOff && (
        <div role="status" className="flex items-start gap-3 rounded-card border border-warning/30 bg-warning/10 p-3 text-sm">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          <p className="flex-1">
            {locationStatus === 'denied' ? 'Location is blocked for this site.' : "Couldn't find your location."} Distances are hidden; results follow the map.
            {locationStatus === 'unavailable' && (
              <button type="button" onClick={onLocate} className="ml-1 font-bold text-info underline-offset-2 hover:underline">
                Try again
              </button>
            )}
          </p>
        </div>
      )}

      {recommendations.length > 0 && (
        <section aria-labelledby="best-heading" className="space-y-3">
          <div>
            <h2 id="best-heading" className="text-base font-bold">
              Best for you now
            </h2>
            <p className="text-xs text-muted">
              Free for the next hour, near {recommendationsFromUser ? 'you' : 'the centre of the map'}.
            </p>
          </div>
          {recommendations.map((rec, index) => (
            <StationCard
              key={rec.station.station_id}
              index={index}
              station={rec.station}
              reason={rec.reason}
              trip={{ minutes: rec.travel_minutes, distanceKm: rec.distance_km, routed: rec.travel_is_routed }}
              isSelected={selectedId === rec.station.station_id}
              onSelect={onSelect}
            />
          ))}
        </section>
      )}

      <section aria-labelledby="all-heading" className="space-y-3">
        <div className="flex items-baseline justify-between gap-2">
          <h2 id="all-heading" className="text-base font-bold">
            Stations in this area
          </h2>
          <p className="num text-xs text-muted" aria-live="polite">
            {loading ? 'Loading…' : refreshing ? 'Updating…' : `${stations.length} shown`}
          </p>
        </div>

        {truncated && (
          <p className="rounded-control bg-raised p-2 text-xs text-muted">Showing the nearest stations only. Zoom in to see more.</p>
        )}

        {loading ? (
          <div role="status" className="space-y-3">
            <span className="sr-only">Loading charging stations…</span>
            <SkeletonBlock className="h-44" />
            <SkeletonBlock className="h-44" />
          </div>
        ) : error && stations.length === 0 ? (
          <Card className="flex flex-col items-center gap-3 p-6 text-center">
            <AlertCircle className="size-9 text-danger" aria-hidden="true" />
            <h3 className="text-base font-bold">Couldn&apos;t load charging stations</h3>
            <p className="text-sm text-muted">{error}</p>
            <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={onRetry}>
              Try again
            </Button>
          </Card>
        ) : stations.length === 0 ? (
          <Card>
            <EmptyState
              icon={<MapPin className="size-7" />}
              title="No stations here"
              text={
                loosen
                  ? `"${loosen.label}" hides every station here. Without it, ${loosen.count} station${loosen.count === 1 ? '' : 's'} show.`
                  : 'Zoom out, move the map, or clear your filters.'
              }
              action={
                loosen ? (
                  <div className="flex flex-wrap justify-center gap-2">
                    <Button onClick={() => onLoosen(loosen.key)}>Show without {loosen.label}</Button>
                    <Button variant="secondary" onClick={onClearFilters}>
                      Clear all filters
                    </Button>
                  </div>
                ) : hasFilters ? (
                  <Button onClick={onClearFilters}>Clear filters</Button>
                ) : undefined
              }
            />
          </Card>
        ) : (
          <div className={refreshing ? 'list-fade space-y-3 opacity-60' : 'list-fade space-y-3'}>
            {error && (
              <p role="alert" className="flex items-center gap-2 text-xs text-danger-soft">
                Couldn&apos;t refresh. Showing earlier results.
                <button type="button" onClick={onRetry} className="font-bold text-info underline-offset-2 hover:underline">
                  Retry
                </button>
              </p>
            )}
            {stations.map((station, index) => (
              <StationCard
                key={station.station_id}
                station={station}
                index={index}
                isSelected={selectedId === station.station_id}
                onSelect={onSelect}
                showDistance={showDistance}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
