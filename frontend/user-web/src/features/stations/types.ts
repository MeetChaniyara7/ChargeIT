import type { components } from '@chargespot/shared';

// Shapes generated from the API (frontend/shared/src/api-types.ts).
type Schemas = components['schemas'];
export type StationSummary = Schemas['StationSummary'];
export type StationDetail = Schemas['StationDetail'];
export type ChargerDetail = Schemas['ChargerDetail'];
export type StationSearchResponse = Schemas['StationSearchResponse'];
export type Recommendation = Schemas['Recommendation'];
export type RecommendationResponse = Schemas['RecommendationResponse'];
export type StationAvailability = Schemas['StationAvailability'];
export type ChargerAvailability = Schemas['ChargerAvailability'];
export type AvailabilityBlock = Schemas['AvailabilityBlock'];
export type BlockState = AvailabilityBlock['state'];
export type Place = Schemas['Place'];
export type GeocodeResponse = Schemas['GeocodeResponse'];
export type SuggestResponse = Schemas['SuggestResponse'];
export type AreaSuggestion = Schemas['AreaSuggestion'];

export interface LatLng {
  lat: number;
  lng: number;
}

/** The part of the world the map is showing. */
export interface MapBounds {
  south: number;
  west: number;
  north: number;
  east: number;
}

/** A request for the map to move: bump `nonce` to move again to the same place. */
export interface MapFocus {
  nonce: number;
  center: LatLng;
  zoom?: number;
  /** If known, fit this area instead of zooming to a point. Nominatim's order: south, north, west, east. */
  bbox?: [number, number, number, number];
}

export type PinSource = Pick<StationSummary, 'station_id' | 'name' | 'latitude' | 'longitude' | 'charger_free' | 'charger_total'>;
