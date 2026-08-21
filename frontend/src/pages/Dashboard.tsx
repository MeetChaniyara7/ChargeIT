import React, { useEffect, useState } from 'react';
import { HeroSearchBar } from '../components/HeroSearchBar';
import { StationCard } from '../components/StationCard';
import type { StationData } from '../components/StationCard';
import { StationMap } from '../components/StationMap';
import { AgentFloatingButton } from '../components/AgentFloatingButton';
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

// Seed dataset fallback if backend API is unreachable or geolocation is pending
const MOCK_SEED_STATIONS: StationData[] = [
  {
    station_id: 'st-01',
    name: 'VoltPulse Supercharge Hub - Downtown',
    address: '101 Electric Ave, Downtown',
    city: 'San Francisco',
    latitude: 37.7749,
    longitude: -122.4194,
    total_chargers: 8,
    available_chargers: 6,
    price_per_kwh: 0.28,
    connector_types: ['CCS2', 'Type 2', 'CHAdeMO'],
  },
  {
    station_id: 'st-02',
    name: 'EcoCharge Plaza - Tech Park',
    address: '450 Innovation Blvd, Financial District',
    city: 'San Francisco',
    latitude: 37.7886,
    longitude: -122.4014,
    total_chargers: 6,
    available_chargers: 4,
    price_per_kwh: 0.24,
    connector_types: ['CCS2', 'Type 2'],
  },
  {
    station_id: 'st-03',
    name: 'GreenDrive Hub - Embarcadero',
    address: '789 Waterfront Way, Embarcadero',
    city: 'San Francisco',
    latitude: 37.7952,
    longitude: -122.3934,
    total_chargers: 4,
    available_chargers: 1,
    price_per_kwh: 0.32,
    connector_types: ['CCS2', 'CHAdeMO'],
  },
  {
    station_id: 'st-04',
    name: 'VoltPulse Express - SOMA Station',
    address: '88 Howard St, SOMA',
    city: 'San Francisco',
    latitude: 37.7825,
    longitude: -122.3971,
    total_chargers: 10,
    available_chargers: 8,
    price_per_kwh: 0.26,
    connector_types: ['CCS2', 'Type 2'],
  },
];

export const Dashboard: React.FC = () => {
  const [stations, setStations] = useState<StationData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
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

  // 2. Fetch Stations from FastAPI Backend (or fallback to seed dataset)
  useEffect(() => {
    const fetchStations = async () => {
      try {
        const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
        const res = await fetch(`${backendUrl}/api/stations`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            const mapped: StationData[] = data.map((item: any) => ({
              station_id: item.station_id,
              name: item.name,
              address: item.address,
              city: item.address?.split(',')[1]?.trim() || 'Local Area',
              latitude: item.latitude,
              longitude: item.longitude,
              total_chargers: item.chargers?.length || 4,
              available_chargers: item.chargers?.filter((c: any) => c.status === 'AVAILABLE').length || 3,
              price_per_kwh: item.chargers?.[0]?.connectors?.[0]?.price_per_kwh || 0.28,
              connector_types: item.chargers?.flatMap((c: any) => c.connectors?.map((conn: any) => conn.connector_type)) || ['CCS2', 'Type 2'],
            }));
            setStations(mapped);
          } else {
            setStations(MOCK_SEED_STATIONS);
          }
        } else {
          setStations(MOCK_SEED_STATIONS);
        }
      } catch (err) {
        setStations(MOCK_SEED_STATIONS);
      } finally {
        setLoading(false);
      }
    };

    fetchStations();
  }, []);

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
        <HeroSearchBar
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
            ) : filteredStations.length === 0 ? (
              /* Empty State */
              <div className="min-h-[350px] glass-card rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-3">
                <MapPin className="w-10 h-10 text-slate-600" />
                <h3 className="text-base font-bold text-white">No Charging Stations Found</h3>
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

      {/* 5. Floating Action Button — "Reserve with Agent" Preview */}
      <AgentFloatingButton />
    </div>
  );
};

export default Dashboard;
