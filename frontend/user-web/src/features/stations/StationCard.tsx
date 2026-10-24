import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Navigation, Star } from 'lucide-react';
import {
  ApproximateTag, availabilityFor, buttonClasses, Card, ConnectorIcon, cx, Money, StatusBadge,
} from '../../components/ui';
import { directionsUrl } from './directions';
import type { StationSummary } from './types';

/** Trip details from a recommendation: real road time, or an estimate when routing was unavailable. */
export interface TripInfo {
  minutes: number;
  distanceKm: number;
  routed: boolean;
}

interface StationCardProps {
  station: StationSummary;
  isSelected?: boolean;
  /** Select this station (and its map pin). A second tap on the selected card opens the station page. */
  onSelect?: (stationId: string) => void;
  /** Show the distance and drive time. Off when we only know the map centre, not where the user is. */
  showDistance?: boolean;
  /** Why this station was recommended, e.g. "2 CCS2 chargers free · 1.2 km · 60 kW". */
  reason?: string;
  trip?: TripInfo;
  /** Position in the list: later cards fade in a moment after earlier ones. */
  index?: number;
  /** Give the card its page address (used to scroll to it). Off for the recommended copy of a station that is also in the list: ids must be unique. */
  anchor?: boolean;
}

const minutesText = (minutes: number, routed: boolean) => `${routed ? '' : '~'}${Math.max(1, Math.round(minutes))} min`;

export const StationCard: React.FC<StationCardProps> = ({ station, isSelected = false, onSelect, showDistance = false, reason, trip, index = 0, anchor = true }) => {
  const free = station.charger_free;
  const total = station.charger_total;
  const distance = trip ? trip.distanceKm : station.distance_km;
  const time = trip ? minutesText(trip.minutes, trip.routed) : station.eta_minutes_estimate ? minutesText(station.eta_minutes_estimate, false) : null;

  return (
    <Card
      id={anchor ? `station-card-${station.station_id}` : undefined}
      elevation={isSelected ? 2 : 1}
      style={{ '--i': Math.min(index, 8) } as React.CSSProperties}
      className={cx(
        'result-enter cursor-pointer p-4 transition-colors duration-150',
        isSelected ? 'result-flash border-primary' : 'hover:border-field-border',
      )}
      onClick={() => onSelect?.(station.station_id)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-bold">
            {/* A real button, so keyboard and screen-reader users can select a station too. */}
            <button
              type="button"
              aria-pressed={isSelected}
              onClick={(e) => {
                e.stopPropagation();
                onSelect?.(station.station_id);
              }}
              className="-my-2.5 rounded py-2.5 text-left hover:text-primary"
            >
              {station.name}
            </button>
          </h3>
          {station.operator_name && <p className="text-sm text-muted">{station.operator_name}</p>}
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted">
            <MapPin className="size-4 shrink-0" aria-hidden="true" />
            <span className="truncate">{station.address || station.city || 'Address unknown'}</span>
          </p>
          {(showDistance || trip) && distance != null && (
            <p className="num mt-0.5 text-sm font-bold text-info">
              {distance.toFixed(1)} km{time && <span className="font-medium"> · {time}</span>}
            </p>
          )}
        </div>
        <StatusBadge
          className="shrink-0"
          status={availabilityFor(free, total)}
          label={total > 0 ? `${free}/${total} free` : 'No chargers'}
        />
      </div>

      {reason && <p className="mt-2 text-sm font-medium text-primary">{reason}</p>}

      <div className="my-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-y border-border py-3">
        <div>
          <p className="text-xs text-muted">From</p>
          <p className="text-base font-bold">
            <Money value={station.min_price_per_kwh} perKwh />
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-sm">
          {station.connector_types.length > 0 ? (
            station.connector_types.map((type) => <ConnectorIcon key={type} type={type} />)
          ) : (
            <span className="text-muted">Plug types unknown</span>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {station.rating != null && (
          <span className="num inline-flex items-center gap-1 text-sm" title={`${station.rating_count} ratings`}>
            <Star className="size-4 fill-warning text-warning" aria-hidden="true" />
            <span className="font-bold">{station.rating.toFixed(1)}</span>
          </span>
        )}
        {station.has_estimated_data && (
          <ApproximateTag reason="Some chargers, power or prices at this station are estimated from typical values for its operator." />
        )}
        <div className="ml-auto flex gap-2">
          <a
            href={directionsUrl(station)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className={buttonClasses({ variant: 'secondary' })}
          >
            <Navigation className="size-4" aria-hidden="true" />
            Navigate
          </a>
          <Link to={`/stations/${station.station_id}`} onClick={(e) => e.stopPropagation()} className={buttonClasses()}>
            View chargers
          </Link>
        </div>
      </div>
    </Card>
  );
};
