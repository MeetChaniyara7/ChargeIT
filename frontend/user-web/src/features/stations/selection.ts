// Which blocks on the slot grid are selected, and whether a tap or drag is allowed.
// Pure functions (no React), so every rule has a test. The API still has the final say:
// the database refuses overlapping bookings. These rules only give instant, friendly feedback.

import type { BlockState, ChargerAvailability } from './types';

/** One booking is 1 to 4 blocks of 30 minutes (docs/architecture.md section 6.2). */
export const MAX_BLOCKS = 4;

export interface Selection {
  chargerId: string;
  /** Start of the first selected block and end of the last one (ISO timestamps). */
  startIso: string;
  endIso: string;
  blocks: number;
}

export type Choice = { ok: true; selection: Selection | null } | { ok: false; message: string };

const WHY_NOT: Record<Exclude<BlockState, 'FREE'>, string> = {
  PAST: 'That time has already passed.',
  BOOKED: 'That block is already booked.',
  HELD: 'Someone is paying for that block right now. Try another one.',
  BUSY_EXTERNAL: "Another driver is charging here right now with the operator's own app.",
  OUT_OF_SERVICE: 'This charger is out of service at that time.',
};

export const TOO_MANY = `You can book up to ${MAX_BLOCKS} blocks (${MAX_BLOCKS * 30 / 60} hours) at a time.`;
export const GAP = "A block in between isn't free, so those times can't be booked together.";

/** The block numbers (first, last) that a selection covers on this charger, or null if it is not on it. */
export function indexesOf(selection: Selection | null, charger: ChargerAvailability): [number, number] | null {
  if (!selection || selection.chargerId !== charger.charger_id) return null;
  const first = charger.blocks.findIndex((b) => b.start === selection.startIso);
  const last = charger.blocks.findIndex((b) => b.end === selection.endIso);
  return first >= 0 && last >= first ? [first, last] : null;
}

function make(charger: ChargerAvailability, from: number, to: number): Choice {
  const low = Math.min(from, to);
  const high = Math.max(from, to);
  const covered = charger.blocks.slice(low, high + 1);
  const blocked = covered.find((b) => b.state !== 'FREE');
  if (blocked) {
    // A single block that is not free explains itself; a range with a hole in it is a "gap".
    return { ok: false, message: low === high && blocked.state !== 'FREE' ? WHY_NOT[blocked.state] : GAP };
  }
  if (covered.length > MAX_BLOCKS) return { ok: false, message: TOO_MANY };
  return {
    ok: true,
    selection: { chargerId: charger.charger_id, startIso: covered[0].start, endIso: covered[covered.length - 1].end, blocks: covered.length },
  };
}

/**
 * A tap (or Enter/Space) on block `index` of a charger:
 * - the first tap picks a block;
 * - a second tap on the same charger picks the other end, selecting everything between;
 * - tapping inside a longer selection restarts from that block; tapping the only selected block clears it.
 */
export function chooseBlock(current: Selection | null, charger: ChargerAvailability, index: number): Choice {
  const block = charger.blocks[index];
  if (!block) return { ok: false, message: 'That block does not exist.' };
  if (block.state !== 'FREE') return { ok: false, message: WHY_NOT[block.state] };

  const covered = indexesOf(current, charger);
  if (!covered) return make(charger, index, index);
  const [first, last] = covered;
  if (index >= first && index <= last) return first === last ? { ok: true, selection: null } : make(charger, index, index);
  return make(charger, Math.min(first, index), Math.max(last, index));
}

/** A drag from one block to another (desktop). */
export function dragBlocks(charger: ChargerAvailability, from: number, to: number): Choice {
  const start = charger.blocks[from];
  if (!start) return { ok: false, message: 'That block does not exist.' };
  if (start.state !== 'FREE') return { ok: false, message: WHY_NOT[start.state] };
  return make(charger, from, to);
}

/** The block numbers a drag in progress would cover, clipped to the longest allowed run of free blocks. */
export function dragPreview(charger: ChargerAvailability, from: number, to: number): [number, number] {
  let low = Math.min(from, to);
  let high = Math.max(from, to);
  const direction = to >= from ? 1 : -1;
  // Stop at the first block that is not free, or after MAX_BLOCKS, so the preview never shows an invalid range.
  const lastGood = (() => {
    let n = from;
    for (let i = from; i !== to + direction; i += direction) {
      if (charger.blocks[i]?.state !== 'FREE' || Math.abs(i - from) + 1 > MAX_BLOCKS) break;
      n = i;
    }
    return n;
  })();
  low = Math.min(from, lastGood);
  high = Math.max(from, lastGood);
  return [low, high];
}
