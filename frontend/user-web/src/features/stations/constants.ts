import { FAST_POWER_KW } from '@chargespot/shared';
import type { ConnectorType } from '@chargespot/shared';
import type { LatLng } from './types';

/** Where the map starts: central Ahmedabad. */
export const DEFAULT_CENTER: LatLng = { lat: 23.0225, lng: 72.5714 };
export const DEFAULT_ZOOM = 12;

/** The plug types offered as filter chips, in the order drivers look for them. */
export const FILTER_CONNECTORS: ConnectorType[] = ['CCS2', 'TYPE2', 'CHADEMO', 'BHARAT_DC001', 'BHARAT_AC001'];

/** "Fast" means at least this many kW (shared with the search parser). */
export const FAST_KW = FAST_POWER_KW;

/** Wait this long after the last key press before asking for search suggestions. */
export const SUGGEST_DEBOUNCE_MS = 250;

/** How many recent searches are remembered in this browser. */
export const RECENT_SEARCH_LIMIT = 5;

/** The most stations asked for at once. Above this the list says "zoom in to see more". */
export const STATION_LIMIT = 500;

/** How long the map must stand still before stations for the new area are requested. */
export const MAP_SETTLE_MS = 400;
