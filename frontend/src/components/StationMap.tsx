import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { StationData } from './StationCard';

interface StationMapProps {
  stations: StationData[];
  userLocation: { lat: number; lng: number } | null;
  selectedStationId: string | null;
  onSelectStation: (stationId: string) => void;
  onReserveClick: (stationId: string) => void;
}

export const StationMap: React.FC<StationMapProps> = ({
  stations,
  userLocation,
  selectedStationId,
  onSelectStation,
  onReserveClick,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<{ [key: string]: L.Marker }>({});

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Initialize Leaflet Map if not already initialized
    if (!mapRef.current) {
      const defaultCenter: [number, number] = userLocation
        ? [userLocation.lat, userLocation.lng]
        : [37.7749, -122.4194];

      const map = L.map(mapContainerRef.current, {
        center: defaultCenter,
        zoom: 12,
        zoomControl: false,
      });

      // Add dark tile layer (CartoDB Dark Matter)
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
      }).addTo(map);

      // Add custom zoom control in top-right
      L.control.zoom({ position: 'topright' }).addTo(map);

      mapRef.current = map;
    }

    const map = mapRef.current;

    // Clear existing station markers
    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};

    // 1. Add User Location Marker (Pulse Ring)
    if (userLocation) {
      const userIcon = L.divIcon({
        className: 'custom-user-marker',
        html: `
          <div style="position: relative; width: 24px; height: 24px;">
            <div style="position: absolute; width: 24px; height: 24px; border-radius: 50%; background: rgba(6, 182, 212, 0.4); animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
            <div style="position: absolute; top: 4px; left: 4px; width: 16px; height: 16px; border-radius: 50%; background: #06b6d4; border: 3px solid #ffffff; box-shadow: 0 0 10px #06b6d4;"></div>
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      L.marker([userLocation.lat, userLocation.lng], { icon: userIcon })
        .addTo(map)
        .bindTooltip('Your Current Location', { permanent: false, direction: 'top' });
    }

    // 2. Add Station Markers
    stations.forEach((st) => {
      const isSelected = st.station_id === selectedStationId;
      const available = st.available_chargers ?? 3;
      const isAvailable = available > 0;
      const pinColor = isSelected ? '#10b981' : isAvailable ? '#06b6d4' : '#ef4444';

      const stationIcon = L.divIcon({
        className: `custom-station-pin-${st.station_id}`,
        html: `
          <div style="
            background: ${pinColor};
            width: ${isSelected ? '36px' : '30px'};
            height: ${isSelected ? '36px' : '30px'};
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #ffffff;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            transition: all 0.2s ease;
          ">
            <div style="transform: rotate(45deg); color: #090d16; font-weight: bold; font-size: 11px;">⚡</div>
          </div>
        `,
        iconSize: [isSelected ? 36 : 30, isSelected ? 36 : 30],
        iconAnchor: [isSelected ? 18 : 15, isSelected ? 36 : 30],
      });

      const marker = L.marker([st.latitude, st.longitude], { icon: stationIcon }).addTo(map);

      // Popup Content
      const popupHtml = `
        <div style="padding: 4px; width: 200px;">
          <h4 style="margin: 0; font-size: 13px; font-weight: bold; color: #ffffff;">${st.name}</h4>
          <p style="margin: 4px 0; font-size: 11px; color: #94a3b8;">${st.address || 'Metro Station'}</p>
          <div style="display: flex; justify-content: space-between; align-items: center; margin: 8px 0; font-size: 11px;">
            <span style="color: #10b981; font-weight: 600;">${st.available_chargers ?? 3}/${st.total_chargers ?? 4} Available</span>
            <span style="color: #ffffff; font-weight: bold;">$${(st.price_per_kwh ?? 0.28).toFixed(2)}/kWh</span>
          </div>
          <button id="pop-nav-${st.station_id}" style="width: 100%; padding: 6px; background: #10b981; color: #ffffff; border: none; border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer; margin-top: 4px;">
            Reserve Slot
          </button>
        </div>
      `;

      marker.bindPopup(popupHtml);

      marker.on('click', () => {
        onSelectStation(st.station_id);
      });

      marker.on('popupopen', () => {
        const btn = document.getElementById(`pop-nav-${st.station_id}`);
        if (btn) {
          btn.onclick = () => onReserveClick(st.station_id);
        }
      });

      markersRef.current[st.station_id] = marker;
    });

    // Center map on selected station if any
    if (selectedStationId && markersRef.current[selectedStationId]) {
      const st = stations.find((s) => s.station_id === selectedStationId);
      if (st) {
        map.setView([st.latitude, st.longitude], 14, { animate: true });
        markersRef.current[selectedStationId].openPopup();
      }
    }
  }, [stations, userLocation, selectedStationId]);

  return (
    <div className="w-full h-full min-h-[400px] lg:min-h-[600px] rounded-2xl overflow-hidden glass-card relative border border-slate-800">
      <div ref={mapContainerRef} className="w-full h-full min-h-[400px] lg:min-h-[600px]" />
    </div>
  );
};
