import { CONNECTOR_LABELS } from '@chargespot/shared';
import { FAST_KW } from './constants';
import { NO_FILTERS } from './useExploreFilters';
import type { ExploreFilters } from './useExploreFilters';

export type FilterKey = keyof typeof NO_FILTERS;

/** Each active filter with a short label, e.g. [{ key: 'operator', label: 'Tata Power' }]. */
export function activeFilters(filters: ExploreFilters): { key: FilterKey; label: string }[] {
  const out: { key: FilterKey; label: string }[] = [];
  if (filters.connectors.length) out.push({ key: 'connectors', label: filters.connectors.map((c) => CONNECTOR_LABELS[c]).join(' / ') });
  if (filters.fast) out.push({ key: 'fast', label: `Fast ${FAST_KW} kW+` });
  if (filters.minKw !== null) out.push({ key: 'minKw', label: `${filters.minKw} kW+` });
  if (filters.maxPrice !== null) out.push({ key: 'maxPrice', label: `Under ₹${filters.maxPrice}/kWh` });
  if (filters.operator) out.push({ key: 'operator', label: filters.operator });
  if (filters.openNow) out.push({ key: 'openNow', label: 'Open now' });
  return out;
}

/** The change that switches one filter off. */
export const withoutFilter = (key: FilterKey): Partial<ExploreFilters> => ({ [key]: NO_FILTERS[key] });
