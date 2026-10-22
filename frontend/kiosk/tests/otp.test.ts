import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CODE_LENGTH, isComplete, otpFailureMessage, pressKey } from '../src/lib/otp.ts';

test('digits are added up to six and then ignored', () => {
  let code = '';
  for (const d of ['1', '2', '3', '4', '5', '6', '7'] as const) code = pressKey(code, d);
  assert.equal(code, '123456');
  assert.equal(code.length, CODE_LENGTH);
  assert.ok(isComplete(code));
});

test('delete removes the last digit and does nothing on an empty pad', () => {
  assert.equal(pressKey('123', 'delete'), '12');
  assert.equal(pressKey('', 'delete'), '');
});

test('clear empties the pad', () => {
  assert.equal(pressKey('12345', 'clear'), '');
  assert.ok(!isComplete('12345'));
});

test('a wrong code says how many tries are left', () => {
  const wrong = (n: number) => otpFailureMessage({ code: 'WRONG_OTP', message: 'x', details: { tries_left: n } });
  assert.equal(wrong(3), 'Wrong code, 3 tries left');
  assert.equal(wrong(1), 'Wrong code, 1 try left');
  assert.equal(otpFailureMessage({ code: 'WRONG_OTP', message: 'x' }), 'Wrong code. Please try again.');
});

test('other failures have plain words, unknown ones use the server message', () => {
  assert.match(otpFailureMessage({ code: 'OTP_NOT_VALID_NOW', message: 'x' }), /15 minutes before/);
  assert.match(otpFailureMessage({ code: 'CHARGER_UNAVAILABLE', message: 'x' }), /cannot start right now/);
  assert.equal(otpFailureMessage({ code: 'SOMETHING', message: 'From the server' }), 'From the server');
});
