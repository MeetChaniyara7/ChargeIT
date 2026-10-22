import assert from 'node:assert/strict';
import { test } from 'node:test';
import { clockMinutes, clockOffsetMs, kwhText, rupees } from '../src/lib/format.ts';

test('whole rupees have no .00, others keep two decimals', () => {
  assert.equal(rupees(186), '₹186');
  assert.equal(rupees(1200), '₹1,200');
  assert.equal(rupees(186.5), '₹186.50');
  assert.equal(rupees(0), '₹0');
});

test('the countdown shows minutes and seconds and never goes below zero', () => {
  assert.equal(clockMinutes(102), '1:42');
  assert.equal(clockMinutes(180), '3:00');
  assert.equal(clockMinutes(59.2), '1:00'); // rounds up: never shows 0:00 while time is left
  assert.equal(clockMinutes(-5), '0:00');
});

test('kWh has one decimal', () => {
  assert.equal(kwhText(32), '32.0 kWh');
  assert.equal(kwhText(5.56), '5.6 kWh');
});

test('the clock follows the server, not the tablet', () => {
  const offset = clockOffsetMs('2026-10-12T10:00:30.000Z', Date.parse('2026-10-12T10:00:00.000Z'));
  assert.equal(offset, 30_000);
});
