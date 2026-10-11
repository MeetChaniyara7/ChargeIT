import React from 'react';
import { MapPin, Navigation, Zap } from 'lucide-react';
import {
  ApproximateTag,
  availabilityFor,
  Button,
  Card,
  ConnectorIcon,
  cx,
  Money,
  StatusBadge,
} from '../../components/ui';
import { directionsUrl } from './directions';

export interface StationData {
  station_id: string;
  name: string;
  address: string;
  city?: string;
  latitude: number;
  longitude: number;
  total_chargers?: number;
  available_chargers?: number;
  price_per_kwh?: number;
  /** Connector type codes, e.g. "CCS2" (ConnectorIcon turns them into labels). */
  connector_types?: string[];
  charger_status_summary?: string;
  distance_km?: number;
  /** True when some shown values were estimated rather than imported. */
  has_estimated_data?: boolean;
}

interface StationCardProps {
  station: StationData;
  onSelect?: (stationId: string) => void;
  onReserveClick?: (stationId: string) => void;
  isSelected?: boolean;
}

export const StationCard: React.FC<StationCardProps> = ({ station, onSelect, onReserveClick, isSelected = false }) => {
  const total = station.total_chargers ?? 0;
  const available = station.available_chargers ?? 0;
  const connectors = station.connector_types ?? [];

  return (
    <Card
      elevation={isSelected ? 2 : 1}
      className={cx('cursor-pointer p-4 transition-colors duration-150', isSelected ? 'border-primary' : 'hover:border-field-border')}
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
              className="rounded text-left hover:text-primary"
            >
              {station.name}
            </button>
          </h3>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted">
            <MapPin className="size-4 shrink-0" aria-hidden="true" />
            <span className="truncate">{station.address || station.city || 'Address unknown'}</span>
            {station.distance_km !== undefined && (
              <>
                <span aria-hidden="true">·</span>
                <span className="num shrink-0 font-bold text-info">{station.distance_km.toFixed(1)} km</span>
              </>
            )}
          </p>
        </div>
        <StatusBadge
          className="shrink-0"
          status={availabilityFor(available, total)}
          label={total > 0 ? `${available}/${total} free` : 'No chargers'}
        />
      </div>

      <div className="my-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-y border-border py-3">
        <div>
          <p className="text-xs text-muted">From</p>
          <p className="text-base font-bold">
            <Money value={station.price_per_kwh} perKwh />
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-sm">
          {connectors.length > 0 ? (
            connectors.map((type) => <ConnectorIcon key={type} type={type} />)
          ) : (
            <span className="text-muted">Plug types unknown</span>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {station.has_estimated_data && (
          <ApproximateTag reason="Some chargers, power or prices at this station are estimated from typical values for its operator." />
        )}
        <div className="ml-auto flex gap-2">
          <Button
            variant="secondary"
            icon={<Navigation className="size-4" aria-hidden="true" />}
            onClick={(e) => {
              e.stopPropagation();
              window.open(directionsUrl(station), '_blank', 'noopener,noreferrer');
            }}
          >
            Navigate
          </Button>
          <Button
            disabled={available === 0}
            icon={<Zap className="size-4" aria-hidden="true" />}
            onClick={(e) => {
              e.stopPropagation();
              onReserveClick?.(station.station_id);
            }}
          >
            Reserve slot
          </Button>
        </div>
      </div>
    </Card>
  );
};
