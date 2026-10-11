// Run with `npm test --workspace @chargespot/shared` (Node's built-in test runner; no extra packages).
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';
import { CHEAP_MAX_PRICE_INR } from '../src/constants.ts';
import { parseSearch, removeToken } from '../src/search.ts';

const kinds = (text: string) => parseSearch(text).tokens.map((t) => t.kind);

describe('plug types', () => {
  const cases: [string, string[]][] = [
    ['ccs2', ['CCS2']],
    ['CCS 2', ['CCS2']],
    ['ccs', ['CCS2']],
    ['combo', ['CCS2']],
    ['type 2', ['TYPE2']],
    ['Type2', ['TYPE2']],
    ['type-2', ['TYPE2']],
    ['chademo', ['CHADEMO']],
    ['CHAdeMO', ['CHADEMO']],
    ['bharat ac', ['BHARAT_AC001']],
    ['ac001', ['BHARAT_AC001']],
    ['bharat dc', ['BHARAT_DC001']],
    ['DC-001', ['BHARAT_DC001']],
    ['gb/t', ['BHARAT_DC001']],
    ['type 1', ['TYPE1']],
    ['dc', ['CCS2', 'CHADEMO', 'BHARAT_DC001']],
    ['ac', ['TYPE2', 'BHARAT_AC001', 'TYPE1']],
  ];
  for (const [input, expected] of cases) {
    test(`"${input}"`, () => {
      const parsed = parseSearch(input);
      assert.deepEqual(parsed.connectors, expected);
      assert.equal(parsed.text, '');
    });
  }

  test('several plugs, each listed once', () => {
    assert.deepEqual(parseSearch('ccs2 or chademo or ccs').connectors, ['CCS2', 'CHADEMO']);
  });
});

describe('power, hours and price', () => {
  test('kW values', () => {
    assert.equal(parseSearch('60kw').minPowerKw, 60);
    assert.equal(parseSearch('60 kW').minPowerKw, 60);
    assert.equal(parseSearch('7.4kw').minPowerKw, 7.4);
    assert.equal(parseSearch('22kw 60kw').minPowerKw, 60);
  });

  test('fast', () => {
    assert.equal(parseSearch('fast').fast, true);
    assert.equal(parseSearch('Rapid').fast, true);
    assert.equal(parseSearch('bopal').fast, false);
  });

  test('opening hours', () => {
    for (const input of ['open now', 'open', 'Open Now', '24x7', '24/7', '24 hours', 'always open']) {
      assert.equal(parseSearch(input).openNow, true, input);
      assert.equal(parseSearch(input).text, '', input);
    }
  });

  test('price', () => {
    assert.equal(parseSearch('cheap').maxPricePerKwh, CHEAP_MAX_PRICE_INR);
    assert.equal(parseSearch('under 15').maxPricePerKwh, 15);
    assert.equal(parseSearch('below ₹12').maxPricePerKwh, 12);
    assert.equal(parseSearch('under rs 18 per kwh').maxPricePerKwh, 18);
    assert.equal(parseSearch('cheap under 9').maxPricePerKwh, 9);
    assert.equal(parseSearch('under 9').text, '');
  });
});

describe('location', () => {
  test('near me', () => {
    for (const input of ['near me', 'nearby', 'Near Me', 'around me', 'nearest']) {
      const parsed = parseSearch(input);
      assert.equal(parsed.nearMe, true, input);
      assert.equal(parsed.placeHint, false, input);
      assert.equal(parsed.text, '', input);
    }
  });

  test('"near <place>" and "in <place>" keep the place as text', () => {
    const near = parseSearch('near Bopal');
    assert.equal(near.text, 'Bopal');
    assert.equal(near.placeHint, true);
    assert.equal(near.nearMe, false);
    assert.equal(parseSearch('in Gandhinagar').text, 'Gandhinagar');
  });

  test('a lone preposition is just text', () => {
    assert.equal(parseSearch('near').text, 'near');
    assert.equal(parseSearch('near').placeHint, false);
  });
});

describe('combinations', () => {
  test('fast ccs2 near Bopal', () => {
    const parsed = parseSearch('fast ccs2 near Bopal');
    assert.deepEqual(parsed.connectors, ['CCS2']);
    assert.equal(parsed.fast, true);
    assert.equal(parsed.text, 'Bopal');
    assert.deepEqual(parsed.tokens.map((t) => t.label), ['Fast 50 kW+', 'CCS2', 'Bopal']);
  });

  test('operator with filters keeps the operator name, with its capitals', () => {
    const parsed = parseSearch('Tata Power open now');
    assert.equal(parsed.text, 'Tata Power');
    assert.equal(parsed.openNow, true);
  });

  test('filler words are dropped, other words kept', () => {
    assert.equal(parseSearch('fast charging stations near Bopal').text, 'Bopal');
    assert.equal(parseSearch('CCS2 chargers with 60kw in Satellite, Ahmedabad').text, 'Satellite, Ahmedabad');
  });

  test('tokens come back in typing order', () => {
    assert.deepEqual(kinds('cheap ccs2 open now near me'), ['price', 'connector', 'open', 'nearMe']);
  });
});

describe('never guess', () => {
  test('empty and blank input', () => {
    for (const input of ['', '   ']) {
      const parsed = parseSearch(input);
      assert.deepEqual(parsed.tokens, []);
      assert.equal(parsed.text, '');
      assert.deepEqual(parsed.connectors, []);
    }
  });

  test('typos and look-alikes stay text', () => {
    for (const input of ['ccs3', 'fst', 'opne', 'chademoo', 'type 3', 'kw', 'Accra', 'Dcm Mall', 'Fastrack', 'Opening Soon']) {
      const parsed = parseSearch(input);
      assert.deepEqual(parsed.tokens, [], input);
      assert.equal(parsed.text, input, input);
    }
  });

  test('punctuation around filters is tidied', () => {
    assert.equal(parseSearch('ccs2, Bopal.').text, 'Bopal');
    assert.equal(parseSearch('  Bopal  ,  ').text, 'Bopal');
  });

  test('a zero price or power is ignored', () => {
    assert.equal(parseSearch('0kw').minPowerKw, undefined);
    assert.equal(parseSearch('under 0').maxPricePerKwh, undefined);
  });
});

describe('removeToken', () => {
  test('takes out one understood part and leaves the rest', () => {
    const input = 'fast ccs2 near Bopal';
    const parsed = parseSearch(input);
    const ccs = parsed.tokens.find((t) => t.kind === 'connector')!;
    assert.equal(removeToken(input, ccs), 'fast near Bopal');
    const place = parsed.tokens.find((t) => t.kind === 'place')!;
    assert.equal(removeToken(input, place), 'fast ccs2');
  });
});
