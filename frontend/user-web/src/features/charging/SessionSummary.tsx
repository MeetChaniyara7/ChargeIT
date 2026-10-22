import React from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Receipt } from 'lucide-react';
import { formatTimeIST } from '@chargespot/shared';
import { buttonClasses, Card, Money } from '../../components/ui';
import { PayBillButton } from './PayBillButton';
import { END_REASONS } from './types';
import type { LiveSession } from './types';

/** The card shown once charging has ended: what was used and what it comes to. */
export const SessionSummary: React.FC<{ session: LiveSession; onPaid?: () => void }> = ({ session, onPaid }) => {
  const total = session.bill_amount ?? session.cost_so_far;
  const due = session.bill_status === 'DUE';
  return (
    <div className="space-y-4">
      <Card elevation={2} className="space-y-3 p-4">
        <p className="flex items-center gap-2 text-sm font-bold">
          <CheckCircle2 className="size-5 text-primary" aria-hidden="true" />
          {session.end_reason ? (END_REASONS[session.end_reason] ?? 'Charging has ended.') : 'Charging has ended.'}
        </p>
        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 border-t border-border pt-3 text-sm">
          <dt className="text-muted">Energy</dt>
          <dd className="num text-right font-medium">{session.energy_kwh.toFixed(2)} kWh</dd>
          <dt className="text-muted">Time</dt>
          <dd className="num text-right font-medium">
            {formatTimeIST(session.started_at)}
            {session.ended_at ? ` to ${formatTimeIST(session.ended_at)}` : ''} ({Math.round(session.duration_minutes)} min)
          </dd>
          <dt className="text-muted">Rate</dt>
          <dd className="text-right font-medium">
            <Money value={session.charger.price_per_kwh} perKwh />
          </dd>
          <dt className="border-t border-border pt-2 text-base font-bold">Total</dt>
          <dd className="border-t border-border pt-2 text-right text-xl font-bold">
            <Money value={total} />
          </dd>
        </dl>
      </Card>

      {due ? (
        <div className="space-y-2">
          <PayBillButton sessionId={session.session_id} amount={total} onPaid={() => onPaid?.()} />
          <p className="text-center text-xs text-muted">Until this bill is paid you cannot book a new slot.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-center text-sm text-muted">
            {session.bill_status === 'PAID' ? 'Paid. Thank you!' : session.bill_status === 'PREPAID_SETTLED' ? 'Paid in advance at the kiosk.' : 'This session needs no payment.'}
          </p>
          {session.source !== 'WALK_IN' && session.bill_status === 'PAID' && (
            <Link to={`/receipts/session/${session.session_id}`} className={buttonClasses({ variant: 'secondary', size: 'lg', fullWidth: true })}>
              <Receipt className="size-4" aria-hidden="true" />
              View receipt
            </Link>
          )}
        </div>
      )}

      <Link to="/bookings" className={buttonClasses({ variant: 'secondary', size: 'lg', fullWidth: true })}>
        My bookings
      </Link>
    </div>
  );
};
