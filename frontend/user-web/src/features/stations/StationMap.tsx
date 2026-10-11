import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { CONNECTOR_LABELS, formatINR } from '@chargespot/shared';
import type { ConnectorType } from '@chargespot/shared';
import { availabilityFor, buttonClasses } from '../../components/ui';
import type { Availability } from '../../components/ui';
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

// Pin colour by availability: the same meaning as the status badges everywhere else.
const PIN_COLOR: Record<Availability, string> = {
  free: 'bg-primary',
  few: 'bg-warning',
  busy: 'bg-danger',
  offline: 'bg-muted',
};

const AVAILABILITY_TEXT: Record<Availability, string> = {
  free: 'text-primary',
  few: 'text-warning',
  busy: 'text-danger',
  offline: 'text-muted',
};

const BOLT = '<path d="M13.2 2 5 13.5h5.3L9.4 22 19 9.8h-5.6z"/>';

/** A teardrop pin with a bolt, coloured by availability and larger when selected. */
const pinHtml = (availability: Availability, selected: boolean): string => {
  const size = selected ? 'size-10 ring-4 ring-info/40' : 'size-8';
  return `
    <div class="${PIN_COLOR[availability]} ${size} flex rotate-[-45deg] items-center justify-center rounded-[50%_50%_50%_0] border-2 border-white shadow-e2">
      <svg viewBox="0 0 24 24" class="size-4 rotate-45 fill-on-primary" aria-hidden="true">${BOLT}</svg>
    </div>`;
};

const userMarkerHtml = `
  <div class="relative size-6">
    <span class="absolute inset-0 animate-ping rounded-full bg-info/40"></span>
    <span class="absolute left-1 top-1 size-4 rounded-full border-[3px] border-white bg-info"></span>
  </div>`;

const popupHtml = (st: StationData): string => {
  const free = st.available_chargers ?? 0;
  const total = st.total_chargers ?? 0;
  const availability = availabilityFor(free, total);
  const connectors = st.connector_types?.length
    ? st.connector_types.map((t) => escapeHtml(CONNECTOR_LABELS[t as ConnectorType] ?? t)).join(', ')
    : 'Unknown';
  const price = st.price_per_kwh !== undefined ? `${formatINR(st.price_per_kwh)}/kWh` : '—';

  return `
    <div class="w-56 p-3">
      <h4 class="pr-4 text-sm font-bold text-fg">${escapeHtml(st.name)}</h4>
      <p class="mt-1 text-xs text-muted">${escapeHtml(st.address || 'Address unknown')}</p>
      <div class="mt-3 flex items-center justify-between text-sm">
        <span class="font-bold ${AVAILABILITY_TEXT[availability]}">${total > 0 ? `${free}/${total} free` : 'No chargers'}</span>
        <span class="num font-bold text-fg">${price}</span>
      </div>
      <p class="mt-2 text-xs text-muted">Plugs: ${connectors}</p>
      ${st.has_estimated_data ? '<p class="mt-2"><span class="rounded-full border border-dotted border-muted px-2 py-0.5 text-xs text-muted">Approximate</span></p>' : ''}
      <button type="button" data-reserve="${escapeHtml(st.station_id)}" class="${buttonClasses({ size: 'md', fullWidth: true })} mt-3">
        Reserve slot
      </button>
    </div>`;
};

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

  // Map events always call the latest handlers without rebuilding the map.
  const handlers = useRef({ onSelectStation, onReserveClick });
  useEffect(() => {
    handlers.current = { onSelectStation, onReserveClick };
  });

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

      L.control.zoom({ position: 'topright' }).addTo(map);

      mapRef.current = map;
      requestAnimationFrame(() => map.invalidateSize());
    }

    const map = mapRef.current;

    // Clear existing markers
    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};
    userMarkerRef.current?.remove();
    userMarkerRef.current = null;

    // Your location
    if (userLocation) {
      const userIcon = L.divIcon({
        className: 'station-pin',
        html: userMarkerHtml,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });
      userMarkerRef.current = L.marker([userLocation.lat, userLocation.lng], { icon: userIcon, title: 'Your location' })
        .addTo(map)
        .bindTooltip('Your location', { permanent: false, direction: 'top' });
    }

    // Stations
    stations.forEach((st) => {
      const isSelected = st.station_id === selectedStationId;
      const availability = availabilityFor(st.available_chargers ?? 0, st.total_chargers ?? 0);
      const px = isSelected ? 40 : 32;

      const stationIcon = L.divIcon({
        className: 'station-pin',
        html: pinHtml(availability, isSelected),
        iconSize: [px, px],
        iconAnchor: [px / 2, px],
        popupAnchor: [0, -px],
      });

      const marker = L.marker([st.latitude, st.longitude], { icon: stationIcon, title: st.name }).addTo(map);
      marker.bindPopup(popupHtml(st), { closeButton: true, minWidth: 224 });

      marker.on('click', () => handlers.current.onSelectStation(st.station_id));
      marker.on('popupopen', () => {
        const button = marker.getPopup()?.getElement()?.querySelector<HTMLButtonElement>('[data-reserve]');
        if (button) button.onclick = () => handlers.current.onReserveClick(st.station_id);
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
      const bounds = L.latLngBounds(stations.map((station): [number, number] => [station.latitude, station.longitude]));
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 14, animate: false });
    }

    requestAnimationFrame(() => map.invalidateSize());
  }, [stations, userLocation, selectedStationId]);

  return (
    <div className="relative h-full min-h-[400px] w-full overflow-hidden rounded-card border border-border bg-surface lg:min-h-[600px]">
      <div ref={mapContainerRef} className="h-full min-h-[400px] w-full lg:min-h-[600px]" />
      {stations.length === 0 && (
        <div className="pointer-events-none absolute inset-0 z-[500] flex items-center justify-center bg-bg/70 px-6 text-center">
          <p className="text-sm font-bold text-muted">No charging stations to show</p>
        </div>
      )}
    </div>
  );
};
