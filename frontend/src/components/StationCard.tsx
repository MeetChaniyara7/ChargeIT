import React from 'react';
import { Navigation, Zap, MapPin } from 'lucide-react';

export interface StationData {
  station_id: string;
  name: string;
  address: string;
  city?: string;
  latitude: number;
  longitude: number;
  total_chargers?: number;
  available_chargers?: number;
  price_per_kwh?: number;
  connector_types?: string[];
  distance_km?: number;
}

interface StationCardProps {
  station: StationData;
  onReserveClick?: (stationId: string) => void;
  isSelected?: boolean;
}

export const StationCard: React.FC<StationCardProps> = ({
  station,
  onReserveClick,
  isSelected = false,
}) => {
  const total = station.total_chargers ?? 4;
  const available = station.available_chargers ?? 3;
  const isAvailable = available > 0;
  const priceDisplay = station.price_per_kwh ? `$${station.price_per_kwh.toFixed(2)}` : '$0.28';
  const connectors = station.connector_types && station.connector_types.length > 0
    ? station.connector_types
    : ['CCS2', 'Type 2'];

  const handleNavigate = (e: React.MouseEvent) => {
    e.stopPropagation();
    const query = encodeURIComponent(`${station.name}, ${station.address}`);
    const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${station.latitude},${station.longitude}&query_place_id=${query}`;
    window.open(googleMapsUrl, '_blank', 'noopener,noreferrer');
  };

  const handleReserve = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onReserveClick) {
      onReserveClick(station.station_id);
    }
  };

  return (
    <div
      className={`p-5 rounded-2xl glass-card transition-all duration-300 relative overflow-hidden group cursor-pointer ${
        isSelected
          ? 'border-emerald-500/60 ring-2 ring-emerald-500/20 shadow-xl shadow-emerald-950/20'
          : 'hover:border-slate-700/80 hover:shadow-2xl'
      }`}
    >
      {/* Top Header: Name, Distance & Area */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight group-hover:text-emerald-300 transition-colors line-clamp-1">
            {station.name}
          </h3>
          <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
            <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <span className="truncate max-w-[200px]">{station.address || station.city || 'Metro Area'}</span>
            {station.distance_km !== undefined && (
              <>
                <span className="text-slate-600">•</span>
                <span className="font-semibold text-cyan-400">{station.distance_km.toFixed(1)} km away</span>
              </>
            )}
          </p>
        </div>

        {/* Live Availability Badge */}
        <div
          className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1.5 shrink-0 border ${
            isAvailable
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isAvailable ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
            }`}
          />
          <span>
            {available}/{total} Available
          </span>
        </div>
      </div>

      {/* Decision-Relevant Info: Starting Price & Connectors Badges */}
      <div className="flex items-center justify-between py-3 border-y border-slate-800/80 my-3">
        {/* Starting Price */}
        <div>
          <span className="text-[10px] uppercase font-semibold tracking-wider text-slate-400 block">
            Starting Price
          </span>
          <span className="text-sm font-bold text-white flex items-baseline gap-0.5">
            {priceDisplay}
            <span className="text-xs font-normal text-slate-400">/kWh</span>
          </span>
        </div>

        {/* Connector Badges Row */}
        <div className="flex items-center gap-1.5 flex-wrap justify-end">
          {connectors.map((conn) => (
            <span
              key={conn}
              className="px-2 py-0.5 rounded-md bg-slate-900/90 text-slate-300 border border-slate-800 text-[11px] font-mono font-medium flex items-center gap-1"
            >
              <Zap className="w-3 h-3 text-amber-400" />
              {conn}
            </span>
          ))}
        </div>
      </div>

      {/* Two Distinct Actions */}
      <div className="grid grid-cols-2 gap-3 mt-4">
        {/* 1. Navigate — Secondary / Outline Style (Instant Google Maps link) */}
        <button
          type="button"
          onClick={handleNavigate}
          className="py-2.5 px-3 rounded-xl bg-slate-800/60 hover:bg-slate-700/80 text-slate-200 border border-slate-700/80 text-xs font-semibold flex items-center justify-center space-x-1.5 transition-all cursor-pointer hover:border-slate-600"
        >
          <Navigation className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>Navigate</span>
        </button>

        {/* 2. Reserve Slot — Primary Style (Triggers /reserve/:stationId stub) */}
        <button
          type="button"
          onClick={handleReserve}
          disabled={!isAvailable}
          className="py-2.5 px-3 rounded-xl gradient-btn text-white text-xs font-semibold flex items-center justify-center space-x-1.5 shadow-md shadow-emerald-950/30 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          <Zap className="w-4 h-4 text-emerald-200 shrink-0 fill-emerald-200" />
          <span>Reserve Slot</span>
        </button>
      </div>
    </div>
  );
};
