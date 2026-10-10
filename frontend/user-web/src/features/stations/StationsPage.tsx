import React, { useEffect, useState } from 'react';
import { apiFetch } from '../../lib/api';
import { SearchBar } from './SearchBar';
import { StationCard } from './StationCard';
import type { StationData } from './StationCard';
import { StationMap } from './StationMap';
import { MapPin, Map, List, AlertCircle, RefreshCw, CheckCircle2, Zap } from 'lucide-react';

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

interface ApiConnector {
  connector_type: string;
  price_per_kwh: number;
  status: string;
}

interface ApiCharger {
  charger_id: string;
  status: string;
  connectors: ApiConnector[];
}

interface ApiStation {
  station_id: string;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  chargers: ApiCharger[];
}

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
  const connectors = chargers.flatMap((charger) =>
    Array.isArray(charger.connectors) ? charger.connectors : []
  );
  const availableConnectors = connectors.filter((connector) => connector.status === 'AVAILABLE');
  const prices = availableConnectors
    .map((connector) => connector.price_per_kwh)
    .filter((price) => Number.isFinite(price));
  const statusCounts = chargers.reduce<Record<string, number>>((counts, charger) => {
    counts[charger.status] = (counts[charger.status] ?? 0) + 1;
    return counts;
  }, {});

  return {
    station_id: String(item.station_id),
    name: item.name,
    address: item.address,
    latitude: item.latitude,
    longitude: item.longitude,
    total_chargers: chargers.length,
    available_chargers: chargers.filter((charger) => charger.status === 'AVAILABLE').length,
    price_per_kwh: prices.length > 0 ? Math.min(...prices) : undefined,
    connector_types: [...new Set(connectors.map((connector) => connector.connector_type))],
    charger_status_summary: Object.entries(statusCounts)
      .map(([status, count]) => `${count} ${status.toLowerCase()}`)
      .join(', '),
  };
};

export const StationsPage: React.FC = () => {
  const [stations, setStations] = useState<StationData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationStatus, setLocationStatus] = useState<'prompt' | 'granted' | 'denied'>('prompt');
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [viewMode, setViewMode] = useState<'both' | 'list' | 'map'>('both');
  const [reservationNotice, setReservationNotice] = useState<string | null>(null);

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

  // Handler for Reserve Slot action stub
  const handleReserveSlot = (stationId: string) => {
    const st = stations.find((s) => s.station_id === stationId);
    setReservationNotice(`Reservation flow stubbed for ${st?.name || 'Station'}. Route: /reserve/${stationId}`);
    setTimeout(() => {
      setReservationNotice(null);
    }, 4000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-white">
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-6 space-y-6">
        {/* 2. Hero Search Bar Component */}
        <SearchBar
          onSearchSubmit={(q) => setSearchQuery(q)}
          onRequestLocation={requestLocation}
          currentCityQuery={searchQuery}
        />

        {/* Reservation Toast Notification Stub */}
        {reservationNotice && (
          <div className="p-4 rounded-xl glass-card bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold flex items-center justify-between animate-fade-in">
            <div className="flex items-center space-x-2.5">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              <span>{reservationNotice}</span>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-200 uppercase font-mono">
              Future Build Stub
            </span>
          </div>
        )}

        {/* Geolocation Fallback Prompt Banner if Denied */}
        {locationStatus === 'denied' && (
          <div className="p-4 rounded-2xl glass-card bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-3">
              <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
              <div>
                <span className="font-bold text-amber-200 block">Location Access Disabled</span>
                Showing stations near default location. Type a city above or enable location for exact distances.
              </div>
            </div>
            <button
              onClick={requestLocation}
              className="px-3 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/30 font-semibold transition-colors cursor-pointer shrink-0"
            >
              Try Location Again
            </button>
          </div>
        )}

        {/* Section Title & Mobile Toggle Controls */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2">
              <Zap className="w-5 h-5 text-emerald-400 stroke-[2.5]" />
              <span>Nearby Charging Stations</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {filteredStations.length} stations found sorted by proximity
            </p>
          </div>

          {/* Mobile View Toggle Buttons (List View / Map View) */}
          <div className="flex items-center bg-slate-900/80 p-1 rounded-xl border border-slate-800 lg:hidden">
            <button
              onClick={() => setViewMode(viewMode === 'list' ? 'both' : 'list')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
                viewMode === 'list'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <List className="w-3.5 h-3.5" />
              <span>List</span>
            </button>
            <button
              onClick={() => setViewMode(viewMode === 'map' ? 'both' : 'map')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
                viewMode === 'map'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Map className="w-3.5 h-3.5" />
              <span>Map</span>
            </button>
          </div>
        </div>

        {/* 3. Hybrid Map + List Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Station List Sidebar (7 Cols on Desktop) */}
          <div
            className={`space-y-4 lg:col-span-7 transition-all ${
              viewMode === 'map' ? 'hidden lg:block' : 'block'
            }`}
          >
            {loading ? (
              <div className="min-h-[350px] glass-card rounded-2xl flex flex-col items-center justify-center space-y-3">
                <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
                <p className="text-xs font-medium text-slate-400">Loading EV charging station network...</p>
              </div>
            ) : fetchError ? (
              <div className="min-h-[350px] glass-card rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-3">
                <AlertCircle className="w-10 h-10 text-rose-400" />
                <h3 className="text-base font-bold text-white">Unable to Load Charging Stations</h3>
                <p className="text-xs text-slate-400 max-w-sm">{fetchError}</p>
                <button
                  onClick={() => setRetryToken((token) => token + 1)}
                  className="px-4 py-2 rounded-xl gradient-btn text-white text-xs font-semibold shadow-md cursor-pointer"
                >
                  Retry
                </button>
              </div>
            ) : filteredStations.length === 0 ? (
              /* Empty State */
              <div className="min-h-[350px] glass-card rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-3">
                <MapPin className="w-10 h-10 text-slate-600" />
                <h3 className="text-base font-bold text-white">No charging stations found</h3>
                <p className="text-xs text-slate-400 max-w-sm">
                  We couldn't find any EV stations matching "{searchQuery}". Try clearing your search or typing a different city.
                </p>
                <button
                  onClick={() => setSearchQuery('')}
                  className="px-4 py-2 rounded-xl gradient-btn text-white text-xs font-semibold shadow-md cursor-pointer"
                >
                  Clear Search Filter
                </button>
              </div>
            ) : (
              /* Render Scrollable Station Cards List */
              <div className="space-y-4 max-h-[650px] overflow-y-auto pr-1 custom-scrollbar">
                {filteredStations.map((station) => (
                  <div
                    key={station.station_id}
                    onClick={() => setSelectedStationId(station.station_id)}
                  >
                    <StationCard
                      station={station}
                      onReserveClick={handleReserveSlot}
                      isSelected={selectedStationId === station.station_id}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Interactive Station Map (5 Cols on Desktop) */}
          <div
            className={`h-[450px] lg:h-[650px] lg:col-span-5 sticky top-20 transition-all ${
              viewMode === 'list' ? 'hidden lg:block' : 'block'
            }`}
          >
            <StationMap
              stations={filteredStations}
              userLocation={userLocation}
              selectedStationId={selectedStationId}
              onSelectStation={(id) => setSelectedStationId(id)}
              onReserveClick={handleReserveSlot}
            />
          </div>
        </div>
      </main>
    </div>
  );
};
