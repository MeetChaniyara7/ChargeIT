import { useCallback, useRef, useState } from 'react';
import { apiFetch, ApiError } from '../../lib/api';
import type { GeocodeResponse, Place } from './types';

export type GeocodeStatus = 'idle' | 'loading' | 'found' | 'none' | 'unavailable';

/**
 * Looks up a place name (e.g. "Bopal") when the user submits the search.
 * Never called while typing: the free geocoder only allows one request per second.
 */
export function useGeocode() {
  const [status, setStatus] = useState<GeocodeStatus>('idle');
  const [places, setPlaces] = useState<Place[]>([]);
  const latest = useRef(0);

  const search = useCallback(async (text: string): Promise<Place[]> => {
    const request = ++latest.current;
    setStatus('loading');
    try {
      const response = await apiFetch<GeocodeResponse>(`/api/geocode?q=${encodeURIComponent(text)}`);
      if (request !== latest.current) return [];
      setPlaces(response.places);
      setStatus(response.places.length > 0 ? 'found' : 'none');
      return response.places;
    } catch (error) {
      if (request !== latest.current) return [];
      // A search that is too short is the user's to fix; everything else is "try again later".
      setStatus(error instanceof ApiError && error.code === 'QUERY_TOO_SHORT' ? 'none' : 'unavailable');
      setPlaces([]);
      return [];
    }
  }, []);

  const clear = useCallback(() => {
    latest.current++;
    setStatus('idle');
    setPlaces([]);
  }, []);

  return { status, places, search, clear };
}
