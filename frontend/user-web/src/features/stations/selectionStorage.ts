import type { Selection } from './selection';

// The driver's pick is remembered for the browser session, so after a hold runs out, a refresh or
// a trip to the Hold & pay page the same blocks are still selected. Storage can be blocked, so
// everything here is allowed to fail quietly.
const key = (stationId: string) => `chargespot:selection:${stationId}`;

export interface SavedSelection {
  selection: Selection;
  /** The IST day tab the blocks are on ("YYYY-MM-DD"). */
  day: string;
}

export function saveSelection(stationId: string, saved: SavedSelection | null): void {
  try {
    if (saved) sessionStorage.setItem(key(stationId), JSON.stringify(saved));
    else sessionStorage.removeItem(key(stationId));
  } catch {
    // Not remembered: harmless.
  }
}

export function loadSelection(stationId: string): SavedSelection | null {
  try {
    const raw = sessionStorage.getItem(key(stationId));
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<SavedSelection>;
    const s = value.selection;
    if (s && typeof s.chargerId === 'string' && typeof s.startIso === 'string' && typeof s.endIso === 'string' && typeof s.blocks === 'number' && typeof value.day === 'string') {
      return { selection: s, day: value.day };
    }
  } catch {
    // Unreadable: ignore it.
  }
  return null;
}
