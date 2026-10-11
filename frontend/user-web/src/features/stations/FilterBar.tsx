import React from 'react';
import { MapPin, X } from 'lucide-react';
import { CONNECTOR_LABELS } from '@chargespot/shared';
import type { ConnectorType } from '@chargespot/shared';
import { Chip, IconButton, Spinner } from '../../components/ui';
import { FAST_KW, FILTER_CONNECTORS } from './constants';
import { SearchBox } from './SearchBox';
import type { SearchBoxProps } from './SearchBox';
import type { GeocodeStatus } from './useGeocode';
import type { ExploreFilters } from './useExploreFilters';
import type { Place } from './types';

interface FilterBarProps {
  filters: ExploreFilters;
  onFiltersChange: (change: Partial<ExploreFilters>) => void;
  search: Omit<SearchBoxProps, 'filters' | 'onFiltersChange'>;
  placeStatus: GeocodeStatus;
  places: Place[];
  onPickPlace: (place: Place) => void;
  onDismissPlaces: () => void;
}

/** A selected filter that came from a typed search (operator, kW, price): shown so it can be removed. */
const RemovableChip: React.FC<{ label: string; onRemove: () => void }> = ({ label, onRemove }) => (
  <button
    type="button"
    onClick={onRemove}
    aria-label={`Remove filter: ${label}`}
    className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full border border-primary bg-primary/15 pl-3 pr-2 text-sm font-medium text-primary"
  >
    {label}
    <X className="size-4" aria-hidden="true" />
  </button>
);

/**
 * The search box and filter chips that float over the map. This is the ONE place frosted
 * glass is used (see docs/ui-flow.md): you can still see the map through it.
 */
export const FilterBar: React.FC<FilterBarProps> = ({
  filters, onFiltersChange, search, placeStatus, places, onPickPlace, onDismissPlaces,
}) => {
  const toggleConnector = (type: ConnectorType, on: boolean) =>
    onFiltersChange({ connectors: on ? [...filters.connectors, type] : filters.connectors.filter((c) => c !== type) });

  // Plugs typed in a search that have no chip of their own (e.g. Type 1) still need to be visible and removable.
  const extraConnectors = filters.connectors.filter((c) => !FILTER_CONNECTORS.includes(c));
  const showPlaces = placeStatus !== 'idle' && !search.open;

  return (
    <div className="absolute inset-x-3 top-3 z-20 flex max-w-md flex-col gap-2">
      <SearchBox {...search} filters={filters} onFiltersChange={onFiltersChange} />

      {!search.open && (
        <div role="group" aria-label="Filters" className="liquid-glass liquid-glass--panel scroll-x-hidden flex gap-2 p-1.5">
          {filters.operator && <RemovableChip label={filters.operator} onRemove={() => onFiltersChange({ operator: '' })} />}
          {FILTER_CONNECTORS.map((type) => (
            <Chip
              key={type}
              className="shrink-0"
              selected={filters.connectors.includes(type)}
              onSelectedChange={(on) => toggleConnector(type, on)}
            >
              {CONNECTOR_LABELS[type]}
            </Chip>
          ))}
          {extraConnectors.map((type) => (
            <RemovableChip key={type} label={CONNECTOR_LABELS[type]} onRemove={() => toggleConnector(type, false)} />
          ))}
          <Chip className="shrink-0" selected={filters.fast} onSelectedChange={(fast) => onFiltersChange({ fast })}>
            Fast {FAST_KW} kW+
          </Chip>
          {filters.minKw !== null && <RemovableChip label={`${filters.minKw} kW+`} onRemove={() => onFiltersChange({ minKw: null })} />}
          {filters.maxPrice !== null && (
            <RemovableChip label={`Under ₹${filters.maxPrice}/kWh`} onRemove={() => onFiltersChange({ maxPrice: null })} />
          )}
          <Chip
            className="shrink-0"
            selected={filters.openNow}
            onSelectedChange={(openNow) => onFiltersChange({ openNow })}
            title="Hides stations known to be closed. Stations with unknown hours stay."
          >
            Open now
          </Chip>
        </div>
      )}

      {showPlaces && (
        <div role="status" className="map-glass p-3 text-sm">
          {placeStatus === 'loading' && (
            <p className="flex items-center gap-2">
              <Spinner className="size-4" /> Searching…
            </p>
          )}
          {placeStatus === 'none' && <p>No places found. Try a different spelling or a nearby area.</p>}
          {placeStatus === 'unavailable' && <p>Place search is unavailable right now. You can still pan the map. Try again shortly.</p>}
          {placeStatus === 'found' && (
            <>
              <div className="flex items-center justify-between gap-2">
                <p className="font-bold">Places found</p>
                <IconButton aria-label="Dismiss places" className="-m-2" onClick={onDismissPlaces}>
                  <X className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
              <ul className="mt-1">
                {places.map((place) => (
                  <li key={`${place.lat},${place.lng},${place.name}`}>
                    <button
                      type="button"
                      onClick={() => onPickPlace(place)}
                      className="flex min-h-11 w-full items-center gap-2 rounded-control px-2 text-left hover:bg-raised"
                    >
                      <MapPin className="size-4 shrink-0 text-muted" aria-hidden="true" />
                      <span className="truncate">{place.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
};
