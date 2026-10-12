import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, CalendarPlus, Check, KeyRound, MapPin, Navigation, RefreshCw } from 'lucide-react';
import { formatTimeIST } from '@chargespot/shared';
import { Button, buttonClasses, Card, SkeletonBlock, StatusBadge } from '../../components/ui';
import { downloadIcs } from '../../lib/calendar';
import { directionsUrl } from '../stations/directions';
import { saveSelection } from '../stations/selectionStorage';
import { CodeTiles } from './CodeTiles';
import { formatSlot } from './format';
import type { BookingOut, TicketState } from './types';
import { useBooking } from './useBookings';

/** A hole punched out of the card's edge, where the dashed tear line meets it. */
const Notch: React.FC<{ side: 'left' | 'right' }> = ({ side }) => (
  <span
    aria-hidden="true"
    className={`absolute top-1/2 size-5 -translate-y-1/2 rounded-full border border-border bg-bg ${side === 'left' ? '-left-2.5' : '-right-2.5'}`}
  />
);

function addToCalendar(booking: BookingOut) {
  downloadIcs({
    id: booking.booking_id,
    title: `EV charging at ${booking.station.name}`,
    location: `${booking.station.name}, ${booking.station.address}`,
    description: `Charger ${booking.charger.label}. Enter your one-time code on the screen at the station from ${formatTimeIST(booking.code_valid_from)}.`,
    startIso: booking.start,
    endIso: booking.end,
  });
}

/**
 * The ticket: a movie-ticket style card with the one-time code in big digit tiles.
 * The code is shown ONCE. It arrives through the page's navigation state, is copied into this page's
 * memory, and is removed from the browser history straight away, so a refresh does not bring it back.
 */
export const TicketPage: React.FC = () => {
  const { bookingId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const query = useBooking(bookingId);
  const [otp] = useState<string | undefined>(() => (location.state as TicketState | null)?.otp);

  useEffect(() => {
    if (otp) navigate(location.pathname, { replace: true, state: null });
    // Only on arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const booking = query.data?.booking;
  const stationId = booking?.station.station_id;
  useEffect(() => {
    // The booking is made, so the remembered pick on the station page is no longer needed.
    if (stationId) saveSelection(stationId, null);
  }, [stationId]);

  if (query.loading) {
    return (
      <div className="mx-auto max-w-md px-4 py-6" role="status">
        <span className="sr-only">Loading your ticket…</span>
        <SkeletonBlock className="h-96" />
      </div>
    );
  }

  if (query.error && !booking) {
    const notFound = /not found|404/i.test(query.error);
    return (
      <div className="mx-auto max-w-md px-4 py-6">
        <Card className="flex flex-col items-center gap-3 p-6 text-center">
          <AlertCircle className="size-9 text-danger" aria-hidden="true" />
          <h1 className="text-base font-bold">{notFound ? "We couldn't find that ticket" : "Couldn't load your ticket"}</h1>
          <p className="text-sm text-muted">{query.error}</p>
          {notFound ? (
            <Link to="/bookings" className={buttonClasses()}>
              My bookings
            </Link>
          ) : (
            <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={query.retry}>
              Try again
            </Button>
          )}
        </Card>
      </div>
    );
  }
  if (!booking) return null;

  const active = booking.status === 'CONFIRMED' || booking.status === 'ACTIVE';

  return (
    <div className="mx-auto max-w-md space-y-4 px-4 py-6">
      <Card elevation={2} className="relative overflow-visible">
        {/* top half: what and when */}
        <div className="space-y-3 p-5 text-center">
          <span
            className={`mx-auto flex size-12 items-center justify-center rounded-full ${active ? 'bg-primary text-on-primary' : 'bg-raised text-muted'}`}
            aria-hidden="true"
          >
            <Check className="size-7" />
          </span>
          <h1 className="text-xl font-bold">{active ? "You're booked" : `Booking ${booking.status.toLowerCase().replace('_', ' ')}`}</h1>
          <div>
            <p className="text-base font-bold">{booking.station.name}</p>
            <p className="mt-0.5 flex items-start justify-center gap-1.5 text-sm text-muted">
              <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {booking.station.address}
            </p>
          </div>
          <dl className="mx-auto grid max-w-xs grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-left text-sm">
            <dt className="text-muted">When</dt>
            <dd className="num text-right font-medium">{formatSlot(booking.start, booking.end)}</dd>
            <dt className="text-muted">Charger</dt>
            <dd className="text-right font-medium">
              {booking.charger.label}
              {booking.charger.power_kw ? ` · ${booking.charger.power_kw} kW` : ''}
            </dd>
          </dl>
        </div>

        {/* the tear line */}
        <div className="relative" aria-hidden="true">
          <Notch side="left" />
          <Notch side="right" />
          <div className="mx-5 border-t-2 border-dashed border-field-border" />
        </div>

        {/* bottom half: the code */}
        <div className="space-y-3 p-5 text-center">
          {active && otp ? (
            <>
              <p className="text-sm font-bold">Your code</p>
              <CodeTiles code={otp} />
              <p className="text-sm text-muted">
                Valid from <span className="num font-bold text-fg">{formatTimeIST(booking.code_valid_from)}</span> to{' '}
                <span className="num font-bold text-fg">{formatTimeIST(booking.code_valid_until)}</span>. Type it on the screen at the station.
              </p>
              <p role="note" className="rounded-control border border-warning/40 bg-warning/10 p-2 text-xs font-medium text-warning">
                This code is shown only once. Screenshot it or note it down. If you lose it, open Bookings and choose Show new code.
              </p>
            </>
          ) : active ? (
            <>
              <KeyRound className="mx-auto size-7 text-muted" aria-hidden="true" />
              <p className="text-sm font-bold">Your code was shown once</p>
              <p className="text-sm text-muted">
                It works from <span className="num font-bold text-fg">{formatTimeIST(booking.code_valid_from)}</span>. Lost it? Open Bookings and choose Show new
                code.
              </p>
            </>
          ) : (
            <StatusBadge status="offline" label={booking.status.replace('_', ' ')} />
          )}
        </div>
      </Card>

      <div className="grid gap-2 sm:grid-cols-2">
        <a href={directionsUrl(booking.station)} target="_blank" rel="noopener noreferrer" className={buttonClasses({ size: 'lg' })}>
          <Navigation className="size-4" aria-hidden="true" />
          Navigate
        </a>
        {active && (
          <Button size="lg" variant="secondary" icon={<CalendarPlus className="size-4" aria-hidden="true" />} onClick={() => addToCalendar(booking)}>
            Add to calendar
          </Button>
        )}
      </div>
      <Link to="/bookings" className={buttonClasses({ variant: 'ghost', fullWidth: true })}>
        My bookings
      </Link>
    </div>
  );
};
