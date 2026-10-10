import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { formatINR } from '@chargespot/shared';
import type { StationData } from './StationCard';

const escapeHtml = (value: string): string =>
  value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  } as Record<string, string>)[character] ?? character);

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
  const userMarkerRef = useRef<L.Marker | null>(null);

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

      // OpenStreetMap's standard tiles: free, no API key, attribution required.
      // A CSS filter (.map-tiles-dark in index.css) darkens them to match the UI.
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        className: 'map-tiles-dark',
        maxZoom: 19,
      }).addTo(map);

      // Add custom zoom control in top-right
      L.control.zoom({ position: 'topright' }).addTo(map);

      mapRef.current = map;
      requestAnimationFrame(() => map.invalidateSize());
    }

    const map = mapRef.current;

    // Clear existing station markers
    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};

    userMarkerRef.current?.remove();
    userMarkerRef.current = null;

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

      userMarkerRef.current = L.marker([userLocation.lat, userLocation.lng], { icon: userIcon })
        .addTo(map)
        .bindTooltip('Your Current Location', { permanent: false, direction: 'top' });
    }

    // 2. Add Station Markers
    stations.forEach((st) => {
      const isSelected = st.station_id === selectedStationId;
      const available = st.available_chargers ?? 0;
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
      const connectorTypes = st.connector_types?.length
        ? st.connector_types.map(escapeHtml).join(', ')
        : 'Not specified';
      const price = st.price_per_kwh !== undefined
        ? `${formatINR(st.price_per_kwh)}/kWh`
        : 'Price unavailable';
      const popupHtml = `
        <div style="padding: 4px; width: 200px;">
          <h4 style="margin: 0; font-size: 13px; font-weight: bold; color: #ffffff;">${escapeHtml(st.name)}</h4>
          <p style="margin: 4px 0; font-size: 11px; color: #94a3b8;">${escapeHtml(st.address || 'Metro Station')}</p>
          <div style="display: flex; justify-content: space-between; align-items: center; margin: 8px 0; font-size: 11px;">
            <span style="color: #10b981; font-weight: 600;">${st.available_chargers ?? 0}/${st.total_chargers ?? 0} Available</span>
            <span style="color: #ffffff; font-weight: bold;">${price}</span>
          </div>
          <p style="margin: 4px 0; font-size: 11px; color: #cbd5e1;">Connectors: ${connectorTypes}</p>
          <p style="margin: 4px 0 8px; font-size: 11px; color: #cbd5e1;">Status: ${escapeHtml(st.charger_status_summary || 'No chargers')}</p>
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

    // Center map on the selected station, user location, or all station markers.
    if (selectedStationId && markersRef.current[selectedStationId]) {
      const st = stations.find((s) => s.station_id === selectedStationId);
      if (st) {
        map.setView([st.latitude, st.longitude], 14, { animate: true });
        markersRef.current[selectedStationId].openPopup();
      }
    } else if (userLocation) {
      map.setView([userLocation.lat, userLocation.lng], 12, { animate: false });
    } else if (stations.length > 0) {
      const bounds = L.latLngBounds(
        stations.map((station): [number, number] => [station.latitude, station.longitude])
      );
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 14, animate: false });
    }

    requestAnimationFrame(() => map.invalidateSize());
  }, [stations, userLocation, selectedStationId]);

  return (
    <div className="w-full h-full min-h-[400px] lg:min-h-[600px] rounded-2xl overflow-hidden glass-card relative border border-slate-800">
      <div ref={mapContainerRef} className="w-full h-full min-h-[400px] lg:min-h-[600px]" />
      {stations.length === 0 && (
        <div className="absolute inset-0 z-[500] flex items-center justify-center bg-slate-950/70 px-6 text-center pointer-events-none">
          <p className="text-sm font-semibold text-slate-300">No charging stations found</p>
        </div>
      )}
    </div>
  );
};
