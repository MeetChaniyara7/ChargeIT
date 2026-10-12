import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, RefreshCw } from 'lucide-react';
import { Button, buttonClasses, Card, Money, SkeletonBlock } from '../../components/ui';
import { formatSlot } from './format';
import { useBooking } from './useBookings';

/** The receipt for a booking fee: what was paid, what was refunded, and what it cost in the end. */
export const ReceiptPage: React.FC = () => {
  const { bookingId } = useParams();
  const query = useBooking(bookingId);
  const booking = query.data?.booking;

  if (query.loading) {
    return (
      <div className="mx-auto max-w-md px-4 py-6" role="status">
        <span className="sr-only">Loading your receipt…</span>
        <SkeletonBlock className="h-64" />
      </div>
    );
  }
  if (!booking) {
    return (
      <div className="mx-auto max-w-md px-4 py-6">
        <Card className="flex flex-col items-center gap-3 p-6 text-center">
          <AlertCircle className="size-9 text-danger" aria-hidden="true" />
          <p className="text-sm text-muted">{query.error ?? "We couldn't find that receipt."}</p>
          <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={query.retry}>
            Try again
          </Button>
        </Card>
      </div>
    );
  }

  const net = Math.max(0, booking.booking_fee - booking.refund_amount);
  return (
    <div className="mx-auto max-w-md space-y-4 px-4 py-6">
      <Link to="/bookings?tab=past" className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-info">
        <ArrowLeft className="size-4" aria-hidden="true" />
        Bookings
      </Link>
      <Card className="space-y-4 p-5">
        <div>
          <h1 className="text-xl font-bold">Receipt</h1>
          <p className="text-sm text-muted">Booking fee for {booking.station.name}</p>
        </div>
        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted">Slot</dt>
          <dd className="num text-right">{formatSlot(booking.start, booking.end)}</dd>
          <dt className="text-muted">Charger</dt>
          <dd className="text-right">{booking.charger.label}</dd>
          <dt className="text-muted">Booking fee paid</dt>
          <dd className="text-right">
            <Money value={booking.booking_fee} />
          </dd>
          {booking.refund_amount > 0 && (
            <>
              <dt className="text-muted">Refunded</dt>
              <dd className="text-right">
                −<Money value={booking.refund_amount} />
              </dd>
            </>
          )}
          <dt className="border-t border-border pt-2 font-bold">You paid in the end</dt>
          <dd className="border-t border-border pt-2 text-right text-base font-bold">
            <Money value={net} />
          </dd>
        </dl>
        {booking.cancel_reason && <p className="text-sm text-muted">{booking.cancel_reason}</p>}
        <p className="text-xs text-muted">Test mode: payments and refunds are recorded, but no real money moves.</p>
      </Card>
      <Link to="/bookings" className={buttonClasses({ variant: 'secondary', fullWidth: true })}>
        My bookings
      </Link>
    </div>
  );
};
