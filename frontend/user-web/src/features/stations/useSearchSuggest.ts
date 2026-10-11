import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { SUGGEST_DEBOUNCE_MS } from './constants';
import type { LatLng, SuggestResponse } from './types';

const MIN_LENGTH = 2;

/** The suggest request for some text, ranked by distance from `reference` when known. */
export function suggestUrl(text: string, reference: LatLng | null): string {
  const params = new URLSearchParams({ q: text });
  if (reference) {
    // About 1 km: moving the map a little doesn't ask again.
    params.set('lat', reference.lat.toFixed(2));
    params.set('lng', reference.lng.toFixed(2));
  }
  return `/api/search/suggest?${params}`;
}

/**
 * Stations, operators and cities matching what is being typed: from our own database
 * only (places are looked up on Enter, never while typing). Waits for a pause in typing,
 * and cancels the request for older text.
 */
export function useSearchSuggest(text: string, reference: LatLng | null, enabled: boolean) {
  const trimmed = text.trim().replace(/\s+/g, ' '); // the API collapses spaces the same way
  const settled = useDebouncedValue(trimmed, SUGGEST_DEBOUNCE_MS);
  const key = enabled && settled.length >= MIN_LENGTH ? suggestUrl(settled, reference) : null;
  const query = useApiQuery(key, (signal) => apiFetch<SuggestResponse>(key as string, { signal }));

  // Only show suggestions for the text that is in the box (or about to be).
  const current = enabled && trimmed.length >= MIN_LENGTH && query.data?.query.toLowerCase() === settled.toLowerCase() ? query.data : undefined;
  return {
    data: current,
    loading: enabled && trimmed.length >= MIN_LENGTH && (settled !== trimmed || query.loading || query.refreshing),
    error: key ? query.error : null,
  };
}
