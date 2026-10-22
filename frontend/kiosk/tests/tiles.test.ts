import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { ChargerTile } from '../src/lib/api.ts';
import { blockedText, doneText, tileText } from '../src/lib/tiles.ts';

const base: ChargerTile = { charger_id: 'c1', label: 'CCS2-1', connector_type: 'CCS2', state: 'FREE', can_walk_in: true, options: [] };
// 2026-10-12 12:30 UTC is 6:00 PM in India (UTC+5:30)
const SIX_PM = '2026-10-12T12:30:00Z';

test('a free charger says until when', () => {
  const t = tileText({ ...base, free_until: SIX_PM });
  assert.deepEqual([t.label, t.tone, t.lines], ['Free', 'free', ['Free until 6:00 PM']]);
  assert.deepEqual(tileText(base).lines, ['Free to use']);
});

test('a reserved charger says for when', () => {
  const t = tileText({ ...base, state: 'RESERVED', reserved_for: SIX_PM });
  assert.deepEqual([t.label, t.tone, t.lines], ['Reserved', 'reserved', ['Reserved for 6:00 PM']]);
});

test('a charging tile shows the walk-in money and the end time', () => {
  const t = tileText({ ...base, state: 'CHARGING', ends_at: SIX_PM, walk_in: { prepaid: 200, used: 120 } });
  assert.deepEqual(t.lines, ['Walk-in · ₹120 of ₹200 used', 'Ends 6:00 PM']);
  assert.deepEqual(tileText({ ...base, state: 'CHARGING' }).lines, ['In use']);
});

test('the other states are in words', () => {
  assert.equal(tileText({ ...base, state: 'PAYING' }).label, 'Being taken');
  assert.deepEqual([tileText({ ...base, state: 'OUT_OF_SERVICE' }).label, tileText({ ...base, state: 'OUT_OF_SERVICE' }).tone], ['Out of service', 'down']);
});

test('a finished walk-in shows what was used and refunded', () => {
  assert.equal(doneText(186, 14), 'Done · used ₹186 · ₹14 refunded');
  assert.equal(doneText(200, 0), 'Done · used ₹200');
  const t = tileText({ ...base, last_walk_in: { used: 186, refunded: 14, ended_at: SIX_PM } });
  assert.equal(t.done, 'Done · used ₹186 · ₹14 refunded');
});

test('reasons a charger cannot take a walk-in', () => {
  assert.equal(blockedText('BOOKED_NOW'), 'Booked right now');
  assert.equal(blockedText('BOOKING_SOON'), 'A booking starts very soon');
  assert.equal(blockedText('PRICE_UNKNOWN'), 'Not available for walk-ins');
  assert.equal(blockedText(null), 'Not available right now');
});
