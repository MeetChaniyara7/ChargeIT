// Run with `npm test --workspace @chargespot/user-web` (Node's built-in test runner).
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';
import { chooseBlock, dragBlocks, dragPreview, GAP, indexesOf, MAX_BLOCKS, TOO_MANY } from '../src/features/stations/selection.ts';
import type { Selection } from '../src/features/stations/selection.ts';

type State = 'FREE' | 'BOOKED' | 'HELD' | 'PAST' | 'OUT_OF_SERVICE';

const HALF_HOUR = 30 * 60 * 1000;
const T0 = Date.UTC(2026, 9, 12, 0, 0);

function charger(id: string, states: State[]) {
  return {
    charger_id: id,
    label: id,
    connector_type: 'CCS2',
    power_kw: 60,
    blocks: states.map((state, i) => ({
      start: new Date(T0 + i * HALF_HOUR).toISOString(),
      end: new Date(T0 + (i + 1) * HALF_HOUR).toISOString(),
      state,
    })),
  };
}

const free = (n: number): State[] => Array<State>(n).fill('FREE');
const pick = (current: Selection | null, c: ReturnType<typeof charger>, index: number) => {
  const result = chooseBlock(current, c, index);
  assert.ok(result.ok, `expected ok, got: ${result.ok ? '' : result.message}`);
  return result.selection;
};

describe('tapping blocks', () => {
  const a = charger('A', free(10));

  test('the first tap picks one block', () => {
    const s = pick(null, a, 3);
    assert.equal(s?.blocks, 1);
    assert.equal(s?.startIso, a.blocks[3].start);
    assert.equal(s?.endIso, a.blocks[3].end);
  });

  test('a second tap picks the other end and selects everything between, either direction', () => {
    const first = pick(null, a, 3);
    assert.deepEqual(indexesOf(pick(first, a, 5), a), [3, 5]);
    assert.deepEqual(indexesOf(pick(first, a, 1), a), [1, 3]);
  });

  test('tapping the only selected block clears it; inside a longer selection restarts from there', () => {
    const one = pick(null, a, 3);
    assert.equal(pick(one, a, 3), null);
    const three = pick(one, a, 5);
    assert.deepEqual(indexesOf(pick(three, a, 4), a), [4, 4]);
  });

  test('tapping a block next to the selection extends it', () => {
    const two = pick(pick(null, a, 3), a, 4);
    assert.deepEqual(indexesOf(pick(two, a, 5), a), [3, 5]);
  });

  test('tapping another charger starts again there', () => {
    const b = charger('B', free(10));
    const s = pick(pick(null, a, 3), b, 6);
    assert.equal(s?.chargerId, 'B');
    assert.equal(s?.blocks, 1);
  });

  test(`you can book up to ${MAX_BLOCKS} blocks and not more`, () => {
    const four = pick(pick(null, a, 2), a, 2 + MAX_BLOCKS - 1);
    assert.equal(four?.blocks, MAX_BLOCKS);
    const tooMany = chooseBlock(pick(null, a, 2), a, 2 + MAX_BLOCKS);
    assert.deepEqual(tooMany, { ok: false, message: TOO_MANY });
    // Extending an existing selection past the limit is refused too, and the selection is left alone.
    assert.equal(chooseBlock(four, a, 2 + MAX_BLOCKS).ok, false);
  });
});

describe('blocks that cannot be chosen', () => {
  const states: State[] = ['PAST', 'FREE', 'FREE', 'BOOKED', 'FREE', 'HELD', 'FREE', 'OUT_OF_SERVICE'];
  const c = charger('A', states);

  test('each state gives its own short reason', () => {
    const reasons = [0, 3, 5, 7].map((i) => {
      const r = chooseBlock(null, c, i);
      assert.equal(r.ok, false);
      return r.ok ? '' : r.message;
    });
    assert.match(reasons[0], /passed/);
    assert.match(reasons[1], /already booked/);
    assert.match(reasons[2], /paying/);
    assert.match(reasons[3], /out of service/);
  });

  test('a range that would cross a booked block is refused', () => {
    const first = pick(null, c, 2);
    assert.deepEqual(chooseBlock(first, c, 4), { ok: false, message: GAP });
  });

  test('the selection survives a refused tap', () => {
    const first = pick(null, c, 1);
    assert.equal(chooseBlock(first, c, 3).ok, false);
    assert.deepEqual(indexesOf(first, c), [1, 1]);
  });

  test('a block that does not exist is refused, not a crash', () => {
    assert.equal(chooseBlock(null, c, 99).ok, false);
    assert.equal(chooseBlock(null, c, -1).ok, false);
  });
});

describe('dragging (desktop)', () => {
  const c = charger('A', ['FREE', 'FREE', 'FREE', 'BOOKED', 'FREE', 'FREE', 'FREE', 'FREE', 'FREE', 'FREE']);

  test('a drag selects the blocks between', () => {
    const r = dragBlocks(c, 0, 2);
    assert.ok(r.ok);
    assert.equal(r.selection?.blocks, 3);
    const backwards = dragBlocks(c, 2, 0);
    assert.ok(backwards.ok && backwards.selection?.startIso === c.blocks[0].start);
  });

  test('a drag across a booked block, or over the limit, is refused', () => {
    assert.deepEqual(dragBlocks(c, 1, 5), { ok: false, message: GAP });
    assert.deepEqual(dragBlocks(c, 4, 9), { ok: false, message: TOO_MANY });
    assert.equal(dragBlocks(c, 3, 4).ok, false); // starts on a booked block
  });

  test('the preview stops at the first blocked block and at the limit', () => {
    assert.deepEqual(dragPreview(c, 0, 6), [0, 2]);
    assert.deepEqual(dragPreview(c, 4, 9), [4, 7]);
    assert.deepEqual(dragPreview(c, 6, 4), [4, 6]);
    assert.deepEqual(dragPreview(c, 2, 2), [2, 2]);
  });
});
