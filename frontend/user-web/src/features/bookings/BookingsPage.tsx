import React from 'react';
import { Link } from 'react-router-dom';
import { Ticket } from 'lucide-react';
import { buttonClasses, EmptyState } from '../../components/ui';

/** Placeholder: bookings arrive with the booking flow. */
export const BookingsPage: React.FC = () => (
  <div className="mx-auto max-w-2xl px-4 py-6">
    <h1 className="text-display font-bold">Bookings</h1>
    <EmptyState
      icon={<Ticket className="size-7" />}
      title="Your bookings will appear here"
      text="Booking opens in an upcoming update. For now you can browse stations on the map."
      action={
        <Link to="/explore" className={buttonClasses()}>
          Find a charger
        </Link>
      }
    />
  </div>
);
