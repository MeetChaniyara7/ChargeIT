import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { Money } from '../../components/ui';
import type { DuesOut } from '../bookings/types';

/** Shown instead of the booking controls while the driver has an unpaid energy bill. */
export const DuesBanner: React.FC<{ dues: DuesOut }> = ({ dues }) => (
  <div role="alert" className="flex items-start gap-3 rounded-card border border-warning/40 bg-warning/10 p-4 text-sm">
    <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden="true" />
    <div>
      <p className="font-bold">
        You have {dues.count === 1 ? 'an unpaid bill' : `${dues.count} unpaid bills`} of <Money value={dues.total} />
      </p>
      <p className="mt-0.5 text-muted">Pay {dues.count === 1 ? 'it' : 'them'} before booking again.</p>
      <Link to="/bookings?tab=due" className="mt-2 inline-flex min-h-11 items-center font-bold text-info underline-offset-2 hover:underline">
        Go to Payment due
      </Link>
    </div>
  </div>
);
