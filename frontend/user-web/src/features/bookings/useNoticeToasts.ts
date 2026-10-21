import { useEffect, useRef } from 'react';
import { useToast } from '../../components/ui';
import type { BookingOut } from './types';

const fingerprint = (booking: BookingOut) => `${booking.notice_kind ?? ''}|${booking.notice_text ?? ''}`;

/**
 * Pops a toast when a booking on screen gets a new notice while the app is open ("Moved from CCS2-1 to
 * CCS2-2, same time."). What was already there when the page opened is not news, so it does not toast.
 */
export function useNoticeToasts(bookings: readonly BookingOut[] | undefined): void {
  const toast = useToast();
  const seen = useRef<Map<string, string> | null>(null);

  useEffect(() => {
    if (!bookings) return;
    const current = new Map(bookings.map((b) => [b.booking_id, fingerprint(b)]));
    const previous = seen.current;
    seen.current = current;
    if (!previous) return;
    for (const booking of bookings) {
      if (!booking.notice_kind || !booking.notice_text) continue;
      if (!previous.has(booking.booking_id) || previous.get(booking.booking_id) === current.get(booking.booking_id)) continue;
      if (booking.notice_kind === 'CANCELLED_NO_CHARGER') toast.error(booking.notice_text);
      else toast.info(booking.notice_text);
    }
  }, [bookings, toast]);
}
