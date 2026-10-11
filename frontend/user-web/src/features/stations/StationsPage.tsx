import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertCircle, List, Map, MapPin, RefreshCw } from 'lucide-react';
import type { components } from '@chargespot/shared';
import { apiFetch } from '../../lib/api';
import { Button, Card, Chip, EmptyState, SkeletonBlock, useToast } from '../../components/ui';
import { SearchBar } from './SearchBar';
import { StationCard } from './StationCard';
import type { StationData } from './StationCard';
import { StationMap } from './StationMap';

// Haversine formula to compute distance in km between two GPS coordinates
const calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

// Shapes generated from the API (frontend/shared/src/api-types.ts). Each charger is one plug.
type ApiStation = components['schemas']['StationResponse'];

const isValidCoordinate = (latitude: number, longitude: number): boolean =>
  Number.isFinite(latitude) && Number.isFinite(longitude) &&
  latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;

const isApiStation = (item: unknown): item is ApiStation => {
  if (typeof item !== 'object' || item === null) return false;
  const station = item as Partial<ApiStation>;
  return typeof station.station_id === 'string' &&
    typeof station.name === 'string' &&
    typeof station.address === 'string' &&
    typeof station.latitude === 'number' &&
    typeof station.longitude === 'number' &&
    Array.isArray(station.chargers);
};

const mapApiStation = (item: ApiStation): StationData | null => {
  if (!isValidCoordinate(item.latitude, item.longitude)) return null;

  const chargers = Array.isArray(item.chargers) ? item.chargers : [];
  const prices = chargers
    .filter((charger) => charger.status === 'AVAILABLE')
    .map((charger) => charger.price_per_kwh)
    .filter((price): price is number => typeof price === 'number' && Number.isFinite(price));
  const statusCounts = chargers.reduce<Record<string, number>>((counts, charger) => {
    counts[charger.status] = (counts[charger.status] ?? 0) + 1;
    return counts;
  }, {});

  return {
    station_id: String(item.station_id),
    name: item.name,
    address: item.address,
    city: item.city ?? undefined,
    latitude: item.latitude,
    longitude: item.longitude,
    total_chargers: chargers.length,
    available_chargers: chargers.filter((charger) => charger.status === 'AVAILABLE').length,
    price_per_kwh: prices.length > 0 ? Math.min(...prices) : undefined,
    connector_types: [...new Set(chargers.map((charger) => charger.connector_type))],
    charger_status_summary: Object.entries(statusCounts)
      .map(([status, count]) => `${count} ${status.toLowerCase()}`)
      .join(', '),
    has_estimated_data: item.has_estimated_data,
  };
};

export const StationsPage: React.FC = () => {
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const [stations, setStations] = useState<StationData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationStatus, setLocationStatus] = useState<'prompt' | 'granted' | 'denied'>('prompt');
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);
  // The landing page search sends people here with ?q=<text>.
  const [searchQuery, setSearchQuery] = useState<string>(searchParams.get('q') ?? '');
  const [viewMode, setViewMode] = useState<'both' | 'list' | 'map'>('both');

  // 1. Request Geolocation on Load
  const requestLocation = () => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(loc);
          setLocationStatus('granted');
        },
        (err) => {
          console.warn('Geolocation denied or error:', err.message);
          setLocationStatus('denied');
          // Default center if location denied: San Francisco coordinates
          setUserLocation({ lat: 37.7749, lng: -122.4194 });
        },
        { timeout: 8000 }
      );
    } else {
      setLocationStatus('denied');
      setUserLocation({ lat: 37.7749, lng: -122.4194 });
    }
  };

  useEffect(() => {
    requestLocation();
  }, []);

  // 2. Fetch stations from the ChargeSpot API.
  useEffect(() => {
    const controller = new AbortController();

    const fetchStations = async () => {
      setLoading(true);
      setFetchError(null);
      try {
        const data = await apiFetch<unknown>('/api/stations', { signal: controller.signal });
        if (!Array.isArray(data)) throw new Error('Station service returned an invalid response');

        const mapped = data
          .filter(isApiStation)
          .map(mapApiStation)
          .filter((station): station is StationData => station !== null);
        const uniqueStations = [...new globalThis.Map<string, StationData>(
          mapped.map((station) => [station.station_id, station])
        ).values()];

        setStations(uniqueStations);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setStations([]);
        setFetchError(err instanceof Error ? err.message : 'Unable to load charging stations');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    fetchStations();
    return () => controller.abort();
  }, [retryToken]);

  // 3. Compute Distances and Sort by Proximity
  const processedStations = stations.map((st) => {
    let distance_km = st.distance_km;
    if (userLocation) {
      distance_km = calculateDistance(userLocation.lat, userLocation.lng, st.latitude, st.longitude);
    }
    return { ...st, distance_km };
  });

  // Filter stations based on search query
  const filteredStations = processedStations
    .filter((st) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        st.name.toLowerCase().includes(q) ||
        st.address.toLowerCase().includes(q) ||
        (st.city && st.city.toLowerCase().includes(q))
      );
    })
    .sort((a, b) => (a.distance_km ?? 0) - (b.distance_km ?? 0));

  // Booking arrives in a later update; say so honestly instead of pretending.
  const handleReserveSlot = (stationId: string) => {
    const st = stations.find((s) => s.station_id === stationId);
    toast.info(`Booking opens in an upcoming update. ${st?.name ?? 'This station'} is on your list.`);
  };

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 px-4 py-6 lg:px-8">
      <SearchBar
        onSearchSubmit={(q) => setSearchQuery(q)}
        onRequestLocation={requestLocation}
        currentCityQuery={searchQuery}
      />

      {/* Shown when location access was refused */}
      {locationStatus === 'denied' && (
        <div role="status" className="flex flex-col items-start justify-between gap-3 rounded-card border border-warning/30 bg-warning/10 p-4 text-sm sm:flex-row sm:items-center">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden="true" />
            <p>
              <span className="block font-bold text-warning">Location is off</span>
              Showing stations near a default location. Search for a place above, or turn on location for exact distances.
            </p>
          </div>
          <Button variant="secondary" onClick={requestLocation} className="shrink-0">
            Try again
          </Button>
        </div>
      )}

      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">Nearby charging stations</h1>
          <p className="num mt-0.5 text-sm text-muted" aria-live="polite">
            {loading ? 'Loading…' : `${filteredStations.length} found, nearest first`}
          </p>
        </div>

        {/* On phones, switch between the list and the map */}
        <div className="flex gap-2 lg:hidden" role="group" aria-label="Show">
          <Chip selected={viewMode === 'list'} onSelectedChange={(on) => setViewMode(on ? 'list' : 'both')}>
            <List className="size-4" aria-hidden="true" />
            List
          </Chip>
          <Chip selected={viewMode === 'map'} onSelectedChange={(on) => setViewMode(on ? 'map' : 'both')}>
            <Map className="size-4" aria-hidden="true" />
            Map
          </Chip>
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        {/* Station list */}
        <div className={`space-y-4 lg:col-span-7 ${viewMode === 'map' ? 'hidden lg:block' : 'block'}`}>
          {loading ? (
            <div role="status" className="space-y-4">
              <span className="sr-only">Loading charging stations…</span>
              <SkeletonBlock className="h-44" />
              <SkeletonBlock className="h-44" />
              <SkeletonBlock className="h-44" />
            </div>
          ) : fetchError ? (
            <Card className="flex flex-col items-center gap-3 p-8 text-center">
              <AlertCircle className="size-10 text-danger" aria-hidden="true" />
              <h2 className="text-xl font-bold">Couldn't load charging stations</h2>
              <p className="max-w-sm text-sm text-muted">{fetchError}</p>
              <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={() => setRetryToken((token) => token + 1)}>
                Try again
              </Button>
            </Card>
          ) : filteredStations.length === 0 ? (
            <Card>
              <EmptyState
                icon={<MapPin className="size-7" />}
                title="No charging stations found"
                text={searchQuery.trim() ? `Nothing matches "${searchQuery.trim()}". Try a different search.` : 'There are no stations to show yet.'}
                action={searchQuery.trim() ? <Button onClick={() => setSearchQuery('')}>Clear search</Button> : undefined}
              />
            </Card>
          ) : (
            <div className="max-h-[650px] space-y-4 overflow-y-auto pr-1">
              {filteredStations.map((station) => (
                <StationCard
                  key={station.station_id}
                  station={station}
                  onSelect={setSelectedStationId}
                  onReserveClick={handleReserveSlot}
                  isSelected={selectedStationId === station.station_id}
                />
              ))}
            </div>
          )}
        </div>

        {/* Map */}
        <div className={`h-[450px] lg:sticky lg:top-20 lg:col-span-5 lg:h-[650px] ${viewMode === 'list' ? 'hidden lg:block' : 'block'}`}>
          <StationMap
            stations={filteredStations}
            userLocation={userLocation}
            selectedStationId={selectedStationId}
            onSelectStation={(id) => setSelectedStationId(id)}
            onReserveClick={handleReserveSlot}
          />
        </div>
      </div>
    </div>
  );
};
