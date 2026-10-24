import assert from 'node:assert/strict';
import { describe, test } from 'node:test';
import { optionalNumber, validateCharger, validateStation } from '../src/features/admin/validation.ts';

const station = { name: 'Hub', address: '', city: '', latitude: '23.02', longitude: '72.57', operatorId: '', openingHours: '' };
const charger = { label: 'CCS2-1', connectorType: 'CCS2', currentType: 'DC', powerKw: '60', pricePerKwh: '18' };

describe('validateStation', () => {
  test('a good station has no errors', () => {
    assert.deepEqual(validateStation(station), {});
  });
  test('the name is required', () => {
    assert.ok(validateStation({ ...station, name: '   ' }).name);
  });
  test('coordinates must be numbers in range', () => {
    assert.ok(validateStation({ ...station, latitude: '' }).latitude);
    assert.ok(validateStation({ ...station, latitude: 'abc' }).latitude);
    assert.ok(validateStation({ ...station, latitude: '91' }).latitude);
    assert.ok(validateStation({ ...station, longitude: '-181' }).longitude);
    assert.deepEqual(validateStation({ ...station, latitude: '-90', longitude: '180' }), {});
  });
  test('long text is refused', () => {
    assert.ok(validateStation({ ...station, name: 'x'.repeat(161) }).name);
    assert.ok(validateStation({ ...station, address: 'x'.repeat(301) }).address);
  });
});

describe('validateCharger', () => {
  test('a good charger has no errors, and power and price may be left empty', () => {
    assert.deepEqual(validateCharger(charger), {});
    assert.deepEqual(validateCharger({ ...charger, powerKw: '', pricePerKwh: '' }), {});
  });
  test('the label and plug are required', () => {
    assert.ok(validateCharger({ ...charger, label: ' ' }).label);
    assert.ok(validateCharger({ ...charger, connectorType: '' }).connectorType);
  });
  test('power must be above zero, price may be zero', () => {
    assert.ok(validateCharger({ ...charger, powerKw: '0' }).powerKw);
    assert.ok(validateCharger({ ...charger, powerKw: '1001' }).powerKw);
    assert.ok(validateCharger({ ...charger, powerKw: 'fast' }).powerKw);
    assert.ok(validateCharger({ ...charger, pricePerKwh: '-1' }).pricePerKwh);
    assert.deepEqual(validateCharger({ ...charger, pricePerKwh: '0' }), {});
  });
});

test('empty text means unknown, not zero', () => {
  assert.equal(optionalNumber(''), null);
  assert.equal(optionalNumber('  '), null);
  assert.equal(optionalNumber('0'), 0);
  assert.equal(optionalNumber('17.5'), 17.5);
});
