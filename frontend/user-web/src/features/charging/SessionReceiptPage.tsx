import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, CheckCircle2, Clock, Printer, RefreshCw } from 'lucide-react';
import { formatDateIST, formatTimeIST } from '@chargespot/shared';
import { Button, Card, Money, SkeletonBlock } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { PayBillButton } from './PayBillButton';
import type { SessionReceipt } from './types';

function useSessionReceipt(sessionId: string | undefined) {
  const key = sessionId ? `/api/me/sessions/${encodeURIComponent(sessionId)}/receipt` : null;
  return useApiQuery(key, (signal) => apiFetch<SessionReceipt>(key as string, { signal }));
}

/**
 * The receipt of a charging session, laid out like a ticket. "Print / save as PDF" uses the browser's own print
 * dialog; the page's print rules (index.css) leave only this card on the paper.
 */
export const SessionReceiptPage: React.FC = () => {
  const { sessionId } = useParams();
  const query = useSessionReceipt(sessionId);
  const receipt = query.data;

  if (query.loading) {
    return (
      <div className="mx-auto max-w-md px-4 py-6" role="status">
        <span className="sr-only">Loading your receipt…</span>
        <SkeletonBlock className="h-96" />
      </div>
    );
  }
  if (!receipt) {
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

  const paid = receipt.bill_status === 'PAID';
  const prepaid = receipt.bill_status === 'PREPAID_SETTLED';
  return (
    <div className="mx-auto max-w-md space-y-4 px-4 py-6">
      <Link to="/bookings?tab=past" className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-info print:hidden">
        <ArrowLeft className="size-4" aria-hidden="true" />
        Bookings
      </Link>

      <Card elevation={2} className="receipt space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-wide text-muted">ChargeSpot receipt</p>
            <h1 className="mt-0.5 text-xl font-bold">{receipt.station_name}</h1>
            <p className="text-sm text-muted">{[receipt.station_address, receipt.station_city].filter(Boolean).join(', ')}</p>
          </div>
          {paid || prepaid ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-control border border-primary/50 px-2 py-1 text-sm font-bold text-primary">
              <CheckCircle2 className="size-4" aria-hidden="true" />
              Paid
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-control border border-warning/60 px-2 py-1 text-sm font-bold text-warning">
              <Clock className="size-4" aria-hidden="true" />
              Payment due
            </span>
          )}
        </div>

        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 border-t border-dashed border-field-border pt-4 text-sm">
          <dt className="text-muted">Charger</dt>
          <dd className="text-right">
            {receipt.charger_label}
            {receipt.power_kw ? ` · ${receipt.power_kw} kW` : ''}
          </dd>
          <dt className="text-muted">Date</dt>
          <dd className="num text-right">{formatDateIST(receipt.started_at)}</dd>
          <dt className="text-muted">Started</dt>
          <dd className="num text-right">{formatTimeIST(receipt.started_at)}</dd>
          <dt className="text-muted">Ended</dt>
          <dd className="num text-right">{formatTimeIST(receipt.ended_at)}</dd>
          <dt className="text-muted">Duration</dt>
          <dd className="num text-right">{Math.round(receipt.duration_minutes)} min</dd>
          <dt className="text-muted">Energy</dt>
          <dd className="num text-right">{receipt.energy_kwh.toFixed(2)} kWh</dd>
          <dt className="text-muted">Rate</dt>
          <dd className="text-right">
            <Money value={receipt.price_per_kwh} perKwh />
          </dd>
          <dt className="border-t border-border pt-3 text-base font-bold">Total</dt>
          <dd className="border-t border-border pt-3 text-right text-xl font-bold">
            <Money value={receipt.total} />
          </dd>
        </dl>

        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 border-t border-dashed border-field-border pt-4 text-sm">
          <dt className="text-muted">Status</dt>
          <dd className="text-right font-bold">{paid ? 'Paid ✓' : prepaid ? 'Paid in advance ✓' : 'Payment due'}</dd>
          {receipt.paid_at && (
            <>
              <dt className="text-muted">Paid on</dt>
              <dd className="num text-right">
                {formatDateIST(receipt.paid_at)}, {formatTimeIST(receipt.paid_at)}
              </dd>
            </>
          )}
          {receipt.payment_reference && (
            <>
              <dt className="text-muted">Payment ID</dt>
              <dd className="break-all text-right font-mono text-xs">{receipt.payment_reference}</dd>
            </>
          )}
          {receipt.booking_fee != null && (
            <>
              <dt className="text-muted">Booking fee (paid earlier)</dt>
              <dd className="text-right">
                <Money value={receipt.booking_fee} />
              </dd>
            </>
          )}
        </dl>
        <p className="text-xs text-muted">Test mode: payments are recorded, but no real money moves. Times are in India time (IST).</p>
      </Card>

      <div className="space-y-2 print:hidden">
        {receipt.bill_status === 'DUE' && <PayBillButton sessionId={receipt.session_id} amount={receipt.total} onPaid={query.refresh} />}
        <Button variant="secondary" size="lg" fullWidth icon={<Printer className="size-4" aria-hidden="true" />} onClick={() => window.print()}>
          Print / save as PDF
        </Button>
      </div>
    </div>
  );
};
