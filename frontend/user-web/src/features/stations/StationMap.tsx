import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { availabilityFor, cx } from '../../components/ui';
import type { Availability } from '../../components/ui';
import type { ExploreView } from './exploreView';
import type { LatLng, MapBounds, MapFocus, PinSource } from './types';

// Pin colour by availability: the same rule and colours as the status badges.
const PIN_COLOR: Record<Availability, string> = {
  free: 'bg-primary',
  few: 'bg-warning',
  busy: 'bg-danger',
  offline: 'bg-muted',
};

const pinLabel = (s: PinSource): string =>
  s.charger_total > 0 ? `${s.name}, ${s.charger_free} of ${s.charger_total} chargers free` : `${s.name}, no chargers listed`;

/** A teardrop pin showing how many chargers are free; the selected pin is bigger with a ring. */
const pinHtml = (s: PinSource, selected: boolean): string => {
  const availability = availabilityFor(s.charger_free, s.charger_total);
  const size = selected ? 'size-11 ring-4 ring-info/50' : 'size-9';
  const count = s.charger_total > 0 ? String(s.charger_free) : '–';
  return `
    <div class="${PIN_COLOR[availability]} ${size} flex rotate-[-45deg] items-center justify-center rounded-[50%_50%_50%_0] border-2 border-white shadow-e2">
      <span class="num rotate-45 text-sm font-bold text-on-primary">${count}</span>
    </div>`;
};

const USER_MARKER_HTML = `
  <div class="relative size-6">
    <span class="absolute inset-0 animate-ping rounded-full bg-info/40"></span>
    <span class="absolute left-1 top-1 size-4 rounded-full border-[3px] border-white bg-info"></span>
  </div>`;

/** What decides how a pin looks. If it hasn't changed, the pin is left alone. */
const pinKey = (s: PinSource, selected: boolean) => `${s.charger_free}/${s.charger_total}/${selected ? 1 : 0}`;

const pinIcon = (s: PinSource, selected: boolean) => {
  const size = selected ? 44 : 36;
  return L.divIcon({ className: 'station-pin', html: pinHtml(s, selected), iconSize: [size, size], iconAnchor: [size / 2, size] });
};

interface PinEntry {
  marker: L.Marker;
  key: string;
}

export interface StationMapProps {
  stations: PinSource[];
  selectedId: string | null;
  userLocation: LatLng | null;
  /** Where the map starts (the last view, or Ahmedabad). Only read when the map is created. */
  initialView: ExploreView;
  /** Bump `focus.nonce` to move the map somewhere. */
  focus: MapFocus | null;
  /** Called after the map has stopped moving (and once when it is ready). */
  onViewChange: (bounds: MapBounds, view: ExploreView) => void;
  onSelect: (stationId: string) => void;
  className?: string;
}

export const StationMap: React.FC<StationMapProps> = ({
  stations, selectedId, userLocation, initialView, focus, onViewChange, onSelect, className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const pinLayerRef = useRef<L.LayerGroup | null>(null);
  const pinsRef = useRef<Map<string, PinEntry>>(new Map());
  const userMarkerRef = useRef<L.Marker | null>(null);

  // Map events always call the latest handlers, without re-creating the map.
  const handlers = useRef({ onViewChange, onSelect });
  useEffect(() => {
    handlers.current = { onViewChange, onSelect };
  });

  // Create the map once.
  useEffect(() => {
    if (!containerRef.current) return;
    const map = L.map(containerRef.current, {
      center: [initialView.center.lat, initialView.center.lng],
      zoom: initialView.zoom,
      zoomControl: false,
    });

    // OpenStreetMap's standard tiles: free, no API key, attribution required.
    // A CSS filter (.map-tiles-dark in index.css) darkens them to match the UI.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      className: 'map-tiles-dark',
      maxZoom: 19,
    }).addTo(map);
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    const report = () => {
      const b = map.getBounds();
      const c = map.getCenter();
      handlers.current.onViewChange(
        { south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() },
        { center: { lat: c.lat, lng: c.lng }, zoom: map.getZoom() },
      );
    };
    map.on('moveend', report);

    pinLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    const pins = pinsRef.current;
    // The container may still be getting its size from the layout.
    requestAnimationFrame(() => {
      map.invalidateSize();
      report();
    });

    return () => {
      map.remove();
      mapRef.current = null;
      pinLayerRef.current = null;
      pins.clear();
      userMarkerRef.current = null;
    };
    // The starting view is only read once, when the map is created.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the pins in step with the stations: add new ones, remove old ones, and refresh a pin
  // ONLY when its free count or selected state changed. Nothing else is rebuilt.
  useEffect(() => {
    const layer = pinLayerRef.current;
    if (!layer) return;
    const pins = pinsRef.current;
    const seen = new Set<string>();

    for (const station of stations) {
      const id = station.station_id;
      const selected = id === selectedId;
      const key = pinKey(station, selected);
      seen.add(id);

      const existing = pins.get(id);
      if (!existing) {
        const marker = L.marker([station.latitude, station.longitude], {
          icon: pinIcon(station, selected),
          title: pinLabel(station),
          alt: pinLabel(station),
          zIndexOffset: selected ? 1000 : 0,
        });
        marker.on('click', () => handlers.current.onSelect(id));
        marker.addTo(layer);
        pins.set(id, { marker, key });
      } else if (existing.key !== key) {
        existing.marker.setIcon(pinIcon(station, selected));
        existing.marker.setZIndexOffset(selected ? 1000 : 0);
        existing.key = key;
      }
    }

    for (const [id, entry] of pins) {
      if (!seen.has(id)) {
        layer.removeLayer(entry.marker);
        pins.delete(id);
      }
    }
  }, [stations, selectedId]);

  // The user's own position.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    userMarkerRef.current?.remove();
    userMarkerRef.current = null;
    if (userLocation) {
      userMarkerRef.current = L.marker([userLocation.lat, userLocation.lng], {
        icon: L.divIcon({ className: 'station-pin', html: USER_MARKER_HTML, iconSize: [24, 24], iconAnchor: [12, 12] }),
        title: 'Your location',
        interactive: false,
        keyboard: false,
      }).addTo(map);
    }
  }, [userLocation]);

  // Move the map when asked.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    if (focus.bbox) {
      const [south, north, west, east] = focus.bbox; // Nominatim's order: south, north, west, east
      map.flyToBounds([[south, west], [north, east]], { maxZoom: 15, duration: 1.4, easeLinearity: 0.2 });
    } else {
      map.flyTo([focus.center.lat, focus.center.lng], focus.zoom ?? 15, { duration: 1.4, easeLinearity: 0.2 });
    }
  }, [focus]);

  // A station picked from the list while off-screen: bring it into view.
  const selectedStation = stations.find((s) => s.station_id === selectedId);
  const selectedLat = selectedStation?.latitude;
  const selectedLng = selectedStation?.longitude;
  useEffect(() => {
    const map = mapRef.current;
    if (map && selectedLat !== undefined && selectedLng !== undefined && !map.getBounds().contains([selectedLat, selectedLng])) {
      map.panTo([selectedLat, selectedLng]);
    }
  }, [selectedId, selectedLat, selectedLng]);

  // `isolate` gives the map its own stacking context. Leaflet's layers use z-index 400–1000,
  // which would otherwise cover the search bar and the bottom sheet floating over the map.
  return <div ref={containerRef} className={cx('isolate h-full w-full', className)} role="application" aria-label="Map of charging stations" />;
};
