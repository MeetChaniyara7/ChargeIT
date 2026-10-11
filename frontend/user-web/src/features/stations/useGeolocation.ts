import { useCallback, useEffect, useRef, useState } from 'react';
import type { LatLng } from './types';

export type LocationStatus = 'idle' | 'asking' | 'granted' | 'denied' | 'unavailable';

export interface Geolocation {
  location: LatLng | null;
  status: LocationStatus;
  /** Ask the browser for the user's position (shows the browser's permission prompt the first time). */
  request: () => void;
}

/**
 * The user's position, only when they ask for it (the "Locate me" button), so nobody gets a
 * permission pop-up the moment the page opens. If they already allowed it on an earlier visit,
 * it is picked up quietly.
 */
export function useGeolocation(onFound?: (location: LatLng) => void): Geolocation {
  const [location, setLocation] = useState<LatLng | null>(null);
  const [status, setStatus] = useState<LocationStatus>('idle');
  const onFoundRef = useRef(onFound);
  useEffect(() => {
    onFoundRef.current = onFound;
  });

  const request = useCallback((notify = true) => {
    if (!('geolocation' in navigator)) {
      setStatus('unavailable');
      return;
    }
    setStatus('asking');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const found = { lat: position.coords.latitude, lng: position.coords.longitude };
        setLocation(found);
        setStatus('granted');
        if (notify) onFoundRef.current?.(found);
      },
      (error) => {
        setStatus(error.code === error.PERMISSION_DENIED ? 'denied' : 'unavailable');
      },
      { timeout: 8000, maximumAge: 60_000 },
    );
  }, []);

  useEffect(() => {
    // Already allowed before? Use it without asking again (and without moving the map).
    navigator.permissions
      ?.query({ name: 'geolocation' })
      .then((permission) => {
        if (permission.state === 'granted') request(false);
      })
      .catch(() => undefined);
  }, [request]);

  return { location, status, request: () => request(true) };
}
