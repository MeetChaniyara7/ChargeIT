import React from 'react';
import { Link } from 'react-router-dom';
import { BatteryCharging, KeyRound, MapPin, Navigation, Receipt, Ticket, X } from 'lucide-react';
import { Button, buttonClasses, Card, Money } from '../../components/ui';
import { directionsUrl } from '../stations/directions';
import { formatSlot } from './format';
import { NoticeBanner } from './NoticeBanner';
import { StatusTimeline } from './StatusTimeline';
import type { BookingOut } from './types';

interface BookingCardProps {
  booking: BookingOut;
  onCancel: (booking: BookingOut) => void;
  onNewCode: (booking: BookingOut) => void;
}

/** A booking as a small ticket: where, when, how far along it is, and what you can do with it. */
export const BookingCard: React.FC<BookingCardProps> = ({ booking, onCancel, onNewCode }) => {
  const live = booking.status === 'HELD' || booking.status === 'CONFIRMED' || booking.status === 'ACTIVE';
  return (
    <Card className="overflow-hidden">
      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-base font-bold">
              <Link to={`/stations/${booking.station.station_id}`} className="hover:text-primary">
                {booking.station.name}
              </Link>
            </h3>
            <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted">
              <MapPin className="size-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{booking.station.address}</span>
            </p>
          </div>
          <div className="shrink-0 text-right text-sm">
            {booking.fee_paid ? <Money value={booking.booking_fee} className="font-bold" /> : booking.source === 'INSTANT' ? <span className="text-muted">No fee</span> : null}
          </div>
        </div>
        <p className="num text-sm font-medium">{formatSlot(booking.start, booking.end)}</p>
        <p className="text-sm text-muted">
          {booking.charger.label}
          {booking.charger.power_kw ? ` · ${booking.charger.power_kw} kW` : ''}
          {booking.source === 'INSTANT' ? ' · Charge now' : ''}
        </p>
        <NoticeBanner kind={booking.notice_kind} text={booking.notice_text} />
        <StatusTimeline status={booking.status} />
        {booking.refund_amount > 0 && (
          <p className="text-sm text-muted">
            Refund recorded: <Money value={booking.refund_amount} className="font-bold text-fg" />
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-2 border-t border-dashed border-field-border bg-raised/40 p-3">
        {booking.status === 'ACTIVE' && booking.session_id && (
          <Link to={`/charging/${booking.session_id}`} className={buttonClasses({ size: 'sm' })}>
            <BatteryCharging className="size-4" aria-hidden="true" />
            Charging now
          </Link>
        )}
        {live && booking.status === 'HELD' && (
          <Link to={`/book/${booking.booking_id}`} className={buttonClasses({ size: 'sm' })}>
            Finish paying
          </Link>
        )}
        {booking.status === 'CONFIRMED' && (
          <>
            <Link to={`/tickets/${booking.booking_id}`} className={buttonClasses({ size: 'sm' })}>
              <Ticket className="size-4" aria-hidden="true" />
              View ticket
            </Link>
            {booking.can_show_new_code && (
              <Button size="sm" variant="secondary" icon={<KeyRound className="size-4" aria-hidden="true" />} onClick={() => onNewCode(booking)}>
                Show new code
              </Button>
            )}
          </>
        )}
        {live && (
          <a href={directionsUrl(booking.station)} target="_blank" rel="noopener noreferrer" className={buttonClasses({ size: 'sm', variant: 'secondary' })}>
            <Navigation className="size-4" aria-hidden="true" />
            Navigate
          </a>
        )}
        {booking.can_cancel && booking.status !== 'HELD' && (
          <Button size="sm" variant="ghost" icon={<X className="size-4" aria-hidden="true" />} onClick={() => onCancel(booking)}>
            Cancel
          </Button>
        )}
        {!live && booking.fee_paid && (
          <Link to={`/receipts/${booking.booking_id}`} className={buttonClasses({ size: 'sm', variant: 'secondary' })}>
            <Receipt className="size-4" aria-hidden="true" />
            Receipt
          </Link>
        )}
        {!live && booking.status !== 'NO_SHOW' && !booking.fee_paid && (
          <Link to={`/stations/${booking.station.station_id}`} className={buttonClasses({ size: 'sm', variant: 'secondary' })}>
            Book again
          </Link>
        )}
      </div>
    </Card>
  );
};
