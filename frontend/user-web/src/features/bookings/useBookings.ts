import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import type { BookingOut, BookingScope, DuesOut } from './types';

/** One booking, plus the moment (on this device's stopwatch) the answer arrived, for the hold countdown. */
export interface BookingWithClock {
  booking: BookingOut;
  /** performance.now() when the response arrived. */
  receivedAt: number;
}

export function useBooking(bookingId: string | undefined) {
  const key = bookingId ? `/api/bookings/${encodeURIComponent(bookingId)}` : null;
  return useApiQuery(key, async (signal): Promise<BookingWithClock> => {
    const booking = await apiFetch<BookingOut>(key as string, { signal });
    return { booking, receivedAt: performance.now() };
  });
}

export function useMyBookings(scope: BookingScope) {
  const key = `/api/me/bookings?scope=${scope}`;
  return useApiQuery(key, (signal) => apiFetch<BookingOut[]>(key, { signal }));
}

/** Unpaid energy bills. While there are any, booking is blocked. */
export function useDues() {
  return useApiQuery('/api/me/dues', (signal) => apiFetch<DuesOut>('/api/me/dues', { signal }));
}
