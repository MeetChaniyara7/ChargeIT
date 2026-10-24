import React, { useState } from 'react';
import { MapPin, SlidersHorizontal, X } from 'lucide-react';
import { CONNECTOR_LABELS } from '@chargespot/shared';
import type { ConnectorType } from '@chargespot/shared';
import { Button, Chip, IconButton, Sheet, Spinner } from '../../components/ui';
import { FAST_KW, FILTER_CONNECTORS, POWER_CHOICES_KW } from './constants';
import { SearchBox } from './SearchBox';
import type { SearchBoxProps } from './SearchBox';
import type { GeocodeStatus } from './useGeocode';
import { NO_FILTERS } from './useExploreFilters';
import type { ExploreFilters } from './useExploreFilters';
import type { Place } from './types';
import { usePopularOperators } from './usePopularOperators';

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

/** One titled group inside the filter popup: the title says what the chips below it filter by. */
const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section aria-label={title} className="space-y-2">
    <h3 className="text-xs font-bold uppercase tracking-wide text-muted">{title}</h3>
    <div className="flex flex-wrap gap-2">{children}</div>
  </section>
);

const sameName = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/**
 * The search box and filter chips that float over the map. This is the ONE place frosted
 * glass is used (see docs/ui-flow.md): you can still see the map through it.
 */
export const FilterBar: React.FC<FilterBarProps> = ({
  filters, onFiltersChange, search, placeStatus, places, onPickPlace, onDismissPlaces,
}) => {
  const [open, setOpen] = useState(false);
  const brands = usePopularOperators();
  // "Fast" (typed in a search, or an old link) is the same as 50 kW+.
  const activeKw = filters.minKw ?? (filters.fast ? FAST_KW : null);
  const toggleConnector = (type: ConnectorType, on: boolean) =>
    onFiltersChange({ connectors: on ? [...filters.connectors, type] : filters.connectors.filter((c) => c !== type) });

  const active: { key: string; label: string; remove: () => void }[] = [
    ...filters.connectors.map((c) => ({ key: `c-${c}`, label: CONNECTOR_LABELS[c], remove: () => toggleConnector(c, false) })),
    ...(filters.operator ? [{ key: 'brand', label: filters.operator, remove: () => onFiltersChange({ operator: '' }) }] : []),
    ...(activeKw !== null ? [{ key: 'kw', label: `${activeKw} kW+`, remove: () => onFiltersChange({ minKw: null, fast: false }) }] : []),
    ...(filters.maxPrice !== null ? [{ key: 'price', label: `Under ₹${filters.maxPrice}/kWh`, remove: () => onFiltersChange({ maxPrice: null }) }] : []),
    ...(filters.openNow ? [{ key: 'open', label: 'Open now', remove: () => onFiltersChange({ openNow: false }) }] : []),
  ];
  const showPlaces = placeStatus !== 'idle' && !search.open;

  return (
    <div className="absolute inset-x-3 top-3 z-20 flex max-w-md flex-col gap-2">
      <SearchBox {...search} filters={filters} onFiltersChange={onFiltersChange} />

      {!search.open && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-haspopup="dialog"
            className="liquid-glass liquid-glass--panel inline-flex min-h-11 shrink-0 items-center gap-2 px-4 text-sm font-semibold"
          >
            <SlidersHorizontal className="size-4" aria-hidden="true" />
            Filters
            {active.length > 0 && (
              <span className="grid size-5 place-items-center rounded-full bg-primary text-xs font-bold text-on-primary" aria-label={`${active.length} on`}>
                {active.length}
              </span>
            )}
          </button>
          {/* What is on right now, each removable with one tap. */}
          <div role="group" aria-label="Active filters" className="scroll-x-hidden flex min-w-0 flex-1 gap-2">
            {active.map((f) => (
              <RemovableChip key={f.key} label={f.label} onRemove={f.remove} />
            ))}
          </div>
        </div>
      )}

      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title="Filters"
        footer={
          <>
            <Button variant="ghost" onClick={() => onFiltersChange({ ...NO_FILTERS })} disabled={active.length === 0}>
              Clear all
            </Button>
            <Button onClick={() => setOpen(false)}>Done</Button>
          </>
        }
      >
        <div className="space-y-5">
          <Section title="Plug type">
            {FILTER_CONNECTORS.map((type) => (
              <Chip key={type} selected={filters.connectors.includes(type)} onSelectedChange={(on) => toggleConnector(type, on)}>
                {CONNECTOR_LABELS[type]}
              </Chip>
            ))}
          </Section>

          {brands.length > 0 && (
            <Section title="Brand">
              {brands.map((brand) => (
                <Chip key={brand.name} selected={sameName(filters.operator, brand.name)} onSelectedChange={(on) => onFiltersChange({ operator: on ? brand.name : '' })}>
                  {brand.name}
                </Chip>
              ))}
            </Section>
          )}

          <Section title="Power">
            {POWER_CHOICES_KW.map((kw) => (
              <Chip
                key={kw}
                selected={activeKw === kw}
                // One power choice at a time; "Fast" (typed in a search) and a typed number are replaced by it.
                onSelectedChange={(on) => onFiltersChange({ fast: false, minKw: on ? kw : null })}
              >
                {kw} kW+
              </Chip>
            ))}
          </Section>

          <Section title="Availability">
            <Chip selected={filters.openNow} onSelectedChange={(openNow) => onFiltersChange({ openNow })} title="Hides stations known to be closed. Stations with unknown hours stay.">
              Open now
            </Chip>
          </Section>
        </div>
      </Sheet>

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
