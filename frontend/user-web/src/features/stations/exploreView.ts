import { DEFAULT_CENTER, DEFAULT_ZOOM } from './constants';
import type { LatLng } from './types';

const KEY = 'chargespot:explore-view';

export interface ExploreView {
  center: LatLng;
  zoom: number;
}

/** Remember where the map was, so coming back from a station page shows the same view. */
export function saveExploreView(view: ExploreView): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(view));
  } catch {
    // Storage can be unavailable (private windows); the map then simply starts at the default view.
  }
}

export function loadExploreView(): ExploreView {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(KEY) ?? 'null') as ExploreView | null;
    if (parsed && Number.isFinite(parsed.center?.lat) && Number.isFinite(parsed.center?.lng) && Number.isFinite(parsed.zoom)) {
      return parsed;
    }
  } catch {
    // fall through to the default
  }
  return { center: DEFAULT_CENTER, zoom: DEFAULT_ZOOM };
}
