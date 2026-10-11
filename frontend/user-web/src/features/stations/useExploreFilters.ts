import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CONNECTOR_TYPES } from '@chargespot/shared';
import type { ConnectorType } from '@chargespot/shared';

export interface ExploreFilters {
  /** Plug types: a station matches if it has ANY of them. Empty = all plugs. */
  connectors: ConnectorType[];
  /** Only chargers of at least FAST_KW. */
  fast: boolean;
  /** Only chargers of at least this many kW (typed, e.g. "60kw"). */
  minKw: number | null;
  /** Only chargers at most this price per kWh in ₹ (typed, e.g. "cheap" or "under 15"). */
  maxPrice: number | null;
  /** Only this operator's stations, e.g. "Tata Power". */
  operator: string;
  /** Hide stations known to be closed right now. */
  openNow: boolean;
  /** The text in the search box (also used to filter the list by name). */
  query: string;
}

export const NO_FILTERS: Omit<ExploreFilters, 'query'> = {
  connectors: [], fast: false, minKw: null, maxPrice: null, operator: '', openNow: false,
};

const positive = (value: string | null): number | null => {
  const n = Number(value);
  return value !== null && Number.isFinite(n) && n > 0 ? n : null;
};

/**
 * The filters live in the page address, e.g.
 * /explore?connector=CCS2&connector=TYPE2&fast=1&min_kw=60&max_price=15&operator=Tata+Power&open=1&q=bopal,
 * so a view can be shared or bookmarked and the back button restores it.
 */
export function useExploreFilters() {
  const [params, setParams] = useSearchParams();

  const connectorKey = params.getAll('connector').join(',');
  const connectors = useMemo(
    () => connectorKey.split(',').filter((c): c is ConnectorType => (CONNECTOR_TYPES as readonly string[]).includes(c)),
    [connectorKey],
  );
  const filters: ExploreFilters = {
    connectors,
    fast: params.get('fast') === '1',
    minKw: positive(params.get('min_kw')),
    maxPrice: positive(params.get('max_price')),
    operator: params.get('operator') ?? '',
    openNow: params.get('open') === '1',
    query: params.get('q') ?? '',
  };

  /** Change some filters. `push` adds a history entry (a submitted search) so Back undoes it. */
  const update = useCallback(
    (change: Partial<ExploreFilters>, options: { push?: boolean } = {}) => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          const setFlag = (key: string, on: boolean | undefined) => {
            if (on === undefined) return;
            if (on) next.set(key, '1');
            else next.delete(key);
          };
          const setValue = (key: string, value: string | number | null | undefined) => {
            if (value === undefined) return;
            const text = value === null ? '' : String(value).trim();
            if (text) next.set(key, text);
            else next.delete(key);
          };
          if (change.connectors) {
            next.delete('connector');
            change.connectors.forEach((c) => next.append('connector', c));
          }
          setFlag('fast', change.fast);
          setFlag('open', change.openNow);
          setValue('min_kw', change.minKw);
          setValue('max_price', change.maxPrice);
          setValue('operator', change.operator);
          setValue('q', change.query);
          return next;
        },
        { replace: !options.push },
      );
    },
    [setParams],
  );

  const clearFilters = useCallback(() => update({ ...NO_FILTERS, query: '' }), [update]);
  const hasFilters =
    filters.connectors.length > 0 || filters.fast || filters.openNow || filters.minKw !== null ||
    filters.maxPrice !== null || filters.operator !== '' || filters.query !== '';

  return { filters, update, clearFilters, hasFilters };
}
