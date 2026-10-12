import assert from 'node:assert/strict';
import { describe, test } from 'node:test';
import { buildIcs } from '../src/lib/calendar.ts';

const event = {
  id: 'abc-123',
  title: 'EV charging at Tata Power – Riya Autolink',
  location: 'Bopal-Ambli Road, Ahmedabad',
  description: 'Charger CCS2-1; code valid from 4:15 PM, shown once.',
  startIso: '2026-10-12T11:00:00Z',
  endIso: '2026-10-12T12:00:00Z',
  now: new Date('2026-10-11T08:00:00Z'),
};

describe('buildIcs', () => {
  const ics = buildIcs(event);

  test('is a calendar with one event, in UTC, with CRLF line ends', () => {
    assert.ok(ics.startsWith('BEGIN:VCALENDAR\r\n') && ics.endsWith('END:VCALENDAR\r\n'));
    assert.equal(ics.match(/BEGIN:VEVENT/g)?.length, 1);
    assert.match(ics, /DTSTART:20261012T110000Z\r\n/);
    assert.match(ics, /DTEND:20261012T120000Z\r\n/);
    assert.match(ics, /DTSTAMP:20261011T080000Z\r\n/);
    assert.match(ics, /UID:abc-123@chargespot\r\n/);
    assert.ok(!ics.replace(/\r\n/g, '').includes('\n'));
  });

  test('escapes commas, semicolons and new lines in text', () => {
    const text = buildIcs({ ...event, title: 'A, B; C\\D', description: 'line 1\nline 2' });
    assert.match(text, /SUMMARY:A\\, B\\; C\\\\D\r\n/);
    assert.match(text, /DESCRIPTION:line 1\\nline 2\r\n/);
  });

  test('has a reminder, 30 minutes before by default', () => {
    assert.match(ics, /BEGIN:VALARM[\s\S]*TRIGGER:-PT30M[\s\S]*END:VALARM/);
    assert.match(buildIcs({ ...event, remindMinutesBefore: 60 }), /TRIGGER:-PT60M/);
  });

  test('long lines are folded at 75 bytes', () => {
    const long = buildIcs({ ...event, description: 'x'.repeat(200) });
    for (const line of long.split('\r\n')) assert.ok(new TextEncoder().encode(line).length <= 75, line);
    assert.ok(long.replace(/\r\n /g, '').includes('x'.repeat(200)));
  });
});
