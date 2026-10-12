// "Add to calendar": builds an .ics file in the browser (no library) that any calendar app opens.
// Format: RFC 5545. Times are written in UTC, so every calendar shows them in the user's own zone.

const pad = (n: number) => String(n).padStart(2, '0');

/** 2026-10-12T10:00:00Z -> "20261012T100000Z" */
function icsTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`;
}

/** Text values need commas, semicolons, backslashes and new lines escaped. */
const escapeText = (text: string) => text.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');

/** Long lines are folded at 75 bytes with a leading space, as the format requires. */
function fold(line: string): string {
  const parts: string[] = [];
  let rest = line;
  while (new TextEncoder().encode(rest).length > 75) {
    let cut = 75;
    while (new TextEncoder().encode(rest.slice(0, cut)).length > 75) cut--;
    parts.push(rest.slice(0, cut));
    rest = ` ${rest.slice(cut)}`;
  }
  parts.push(rest);
  return parts.join('\r\n');
}

export interface CalendarEvent {
  id: string;
  title: string;
  location: string;
  description: string;
  startIso: string;
  endIso: string;
  /** Minutes before the start to remind. */
  remindMinutesBefore?: number;
  /** For tests: the "created" time. */
  now?: Date;
}

export function buildIcs(event: CalendarEvent): string {
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//ChargeSpot//Booking//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${event.id}@chargespot`,
    `DTSTAMP:${icsTime((event.now ?? new Date()).toISOString())}`,
    `DTSTART:${icsTime(event.startIso)}`,
    `DTEND:${icsTime(event.endIso)}`,
    `SUMMARY:${escapeText(event.title)}`,
    `LOCATION:${escapeText(event.location)}`,
    `DESCRIPTION:${escapeText(event.description)}`,
    'BEGIN:VALARM',
    'ACTION:DISPLAY',
    `DESCRIPTION:${escapeText(event.title)}`,
    `TRIGGER:-PT${event.remindMinutesBefore ?? 30}M`,
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  ];
  return `${lines.map(fold).join('\r\n')}\r\n`;
}

/** Offers the file to the browser as a download. */
export function downloadIcs(event: CalendarEvent, filename = 'chargespot-booking.ics'): void {
  const url = URL.createObjectURL(new Blob([buildIcs(event)], { type: 'text/calendar;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
