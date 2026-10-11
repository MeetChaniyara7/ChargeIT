import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Car } from 'lucide-react';
import { EmptyState } from '../../components/ui';

/** Placeholder: adding and editing vehicles arrives with the booking flow. */
export const VehiclesPage: React.FC = () => (
  <div className="mx-auto max-w-2xl px-4 py-6">
    <Link to="/profile" className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-info">
      <ArrowLeft className="size-4" aria-hidden="true" />
      Profile
    </Link>
    <h1 className="text-display font-bold">My vehicles</h1>
    <EmptyState
      icon={<Car className="size-7" />}
      title="Your vehicles will appear here"
      text="Soon you'll add your car, so ChargeSpot can show only the chargers that fit its plug."
    />
  </div>
);
