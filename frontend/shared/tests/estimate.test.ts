import assert from 'node:assert/strict';
import { describe, test } from 'node:test';
import { estimateEnergy } from '../src/estimate.ts';

describe('estimateEnergy', () => {
  test('power x time x efficiency x price', () => {
    // 60 kW for 1 hour at 90% = 54 kWh, at ₹20/kWh = ₹1080
    const result = estimateEnergy({ powerKw: 60, pricePerKwh: 20, minutes: 60 });
    assert.deepEqual(result, { kwh: 54, cost: 1080, limitedByBattery: false });
  });

  test('the battery size caps the energy', () => {
    const result = estimateEnergy({ powerKw: 60, pricePerKwh: 20, minutes: 60, batteryKwh: 40 });
    assert.deepEqual(result, { kwh: 40, cost: 800, limitedByBattery: true });
  });

  test('a battery bigger than the energy changes nothing', () => {
    assert.equal(estimateEnergy({ powerKw: 7.4, pricePerKwh: 10, minutes: 30, batteryKwh: 40 })?.limitedByBattery, false);
  });

  test('rounds the cost to paise', () => {
    // 22 kW for 30 minutes at 90% = 9.9 kWh; at ₹17.33/kWh = 171.567 -> 171.57
    assert.equal(estimateEnergy({ powerKw: 22, pricePerKwh: 17.33, minutes: 30 })?.cost, 171.57);
  });

  test('unknown power or price gives no estimate, never an invented one', () => {
    assert.equal(estimateEnergy({ powerKw: null, pricePerKwh: 20, minutes: 60 }), null);
    assert.equal(estimateEnergy({ powerKw: 60, pricePerKwh: undefined, minutes: 60 }), null);
    assert.equal(estimateEnergy({ powerKw: 0, pricePerKwh: 20, minutes: 60 }), null);
    assert.equal(estimateEnergy({ powerKw: 60, pricePerKwh: 20, minutes: 0 }), null);
  });

  test('a free charger (price 0) is a valid estimate of ₹0', () => {
    assert.equal(estimateEnergy({ powerKw: 7, pricePerKwh: 0, minutes: 60 })?.cost, 0);
  });
});
