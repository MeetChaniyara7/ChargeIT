// What a charger tile says. Pure, so the wording is unit-tested; the tile only draws it.

import { formatTimeIST } from '@chargespot/shared';
import type { ChargerTile } from './api';
import { rupees } from './format.ts';

export type Tone = 'free' | 'reserved' | 'charging' | 'paying' | 'down';

export interface TileText {
  /** The state in words (colour is never the only signal). */
  label: string;
  tone: Tone;
  /** Lines under the state: free-until, reserved-for, ends-at, walk-in money... */
  lines: string[];
  /** A walk-in that just finished: "Done · used ₹186 · ₹14 refunded". */
  done: string | null;
}

export function doneText(used: number, refunded: number): string {
  return refunded > 0 ? `Done · used ${rupees(used)} · ${rupees(refunded)} refunded` : `Done · used ${rupees(used)}`;
}

export function tileText(tile: ChargerTile): TileText {
  const done = tile.last_walk_in ? doneText(tile.last_walk_in.used, tile.last_walk_in.refunded) : null;
  switch (tile.state) {
    case 'FREE':
      return {
        label: 'Free',
        tone: 'free',
        lines: [tile.free_until ? `Free until ${formatTimeIST(tile.free_until)}` : 'Free to use'],
        done,
      };
    case 'RESERVED':
      return {
        label: 'Reserved',
        tone: 'reserved',
        lines: [tile.reserved_for ? `Reserved for ${formatTimeIST(tile.reserved_for)}` : 'Reserved for a booking'],
        done,
      };
    case 'CHARGING': {
      const lines: string[] = [];
      if (tile.walk_in) lines.push(`Walk-in · ${rupees(tile.walk_in.used)} of ${rupees(tile.walk_in.prepaid)} used`);
      if (tile.ends_at) lines.push(`Ends ${formatTimeIST(tile.ends_at)}`);
      return { label: 'Charging', tone: 'charging', lines: lines.length ? lines : ['In use'], done: null };
    }
    case 'PAYING':
      return { label: 'Being taken', tone: 'paying', lines: ['Someone is paying at the kiosk'], done: null };
    case 'OUT_OF_SERVICE':
      return { label: 'Out of service', tone: 'down', lines: ['Please use another charger'], done };
  }
}

/** Why a charger cannot take a walk-in, in words for the "no chargers" screen. */
export function blockedText(reason: string | null | undefined): string {
  switch (reason) {
    case 'PRICE_UNKNOWN':
    case 'POWER_UNKNOWN':
      return 'Not available for walk-ins';
    case 'BOOKED_NOW':
      return 'Booked right now';
    case 'BOOKING_SOON':
      return 'A booking starts very soon';
    default:
      return 'Not available right now';
  }
}
