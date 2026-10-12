import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button, Money, Sheet, SkeletonLine, useToast } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { CodeTiles } from './CodeTiles';
import { formatSlot } from './format';
import type { BookingOut, OtpOut, RefundPreview } from './types';

interface CancelSheetProps {
  booking: BookingOut | null;
  onClose: () => void;
  /** Called after the booking was cancelled, so the list can refresh. */
  onCancelled: () => void;
}

/** Cancel a booking: shows what you would get back, and why, before you confirm. */
export const CancelSheet: React.FC<CancelSheetProps> = ({ booking, onClose, onCancelled }) => {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = booking ? `/api/bookings/${booking.booking_id}/cancel-preview` : null;
  const preview = useApiQuery(key, (signal) => apiFetch<RefundPreview>(key as string, { signal }));
  const refund = key && preview.data?.booking_id === booking?.booking_id ? preview.data : undefined;

  const confirm = async () => {
    if (!booking) return;
    setBusy(true);
    setError(null);
    try {
      const done = await apiFetch<RefundPreview>(`/api/bookings/${booking.booking_id}/cancel`, { method: 'POST' });
      toast.success(done.refund_amount > 0 ? `Booking cancelled. ₹${done.refund_amount.toFixed(2)} refund recorded.` : 'Booking cancelled.');
      onCancelled();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not cancel. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={booking !== null}
      onClose={onClose}
      title="Cancel this booking?"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Keep it
          </Button>
          <Button variant="danger" loading={busy} disabled={!refund} onClick={() => void confirm()}>
            Cancel booking
          </Button>
        </>
      }
    >
      {booking && (
        <div className="space-y-3">
          <p className="text-sm">
            <span className="font-bold">{booking.station.name}</span>
            <span className="num block text-muted">
              {booking.charger.label} · {formatSlot(booking.start, booking.end)}
            </span>
          </p>
          {preview.loading || (key && !refund && !preview.error) ? (
            <div role="status" className="space-y-2">
              <span className="sr-only">Working out your refund…</span>
              <SkeletonLine className="h-6 w-2/3" />
              <SkeletonLine className="h-4 w-full" />
            </div>
          ) : preview.error && !refund ? (
            <p role="alert" className="text-sm font-medium text-danger-soft">
              {preview.error}
            </p>
          ) : refund ? (
            <div className="rounded-card border border-border bg-raised p-3">
              <p className="text-base font-bold">
                {refund.refund_amount > 0 ? (
                  <>
                    You will get <Money value={refund.refund_amount} /> back
                  </>
                ) : (
                  'No refund'
                )}
              </p>
              <p className="mt-1 text-sm text-muted">{refund.reason}</p>
              {refund.fee_paid > 0 && (
                <p className="mt-1 text-xs text-muted">
                  Booking fee paid: <Money value={refund.fee_paid} />. Refunds are recorded in test mode and no real money moves.
                </p>
              )}
            </div>
          ) : null}
          {error && (
            <p role="alert" className="text-sm font-medium text-danger-soft">
              {error}
            </p>
          )}
        </div>
      )}
    </Sheet>
  );
};

interface NewCodeSheetProps {
  booking: BookingOut | null;
  onClose: () => void;
}

/** "Show new code": asks first, because the old code stops working; then shows the new one once. */
export const NewCodeSheet: React.FC<NewCodeSheetProps> = ({ booking, onClose }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<OtpOut | null>(null);

  const close = () => {
    setIssued(null);
    setError(null);
    onClose();
  };

  const show = async () => {
    if (!booking) return;
    setBusy(true);
    setError(null);
    try {
      setIssued(await apiFetch<OtpOut>(`/api/bookings/${booking.booking_id}/otp`, { method: 'POST' }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not get a new code. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={booking !== null}
      onClose={close}
      title={issued ? 'Your new code' : 'Show a new code?'}
      footer={
        issued ? (
          <Button onClick={close}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={close} disabled={busy}>
              Not now
            </Button>
            <Button loading={busy} onClick={() => void show()}>
              Show new code
            </Button>
          </>
        )
      }
    >
      {issued ? (
        <div className="space-y-3 text-center">
          <CodeTiles code={issued.otp} />
          <p className="text-sm text-muted">
            Type this on the screen at the station. It is shown once, and your old code no longer works.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="flex items-start gap-2 text-sm">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
            <span>Your old code will stop working as soon as you show a new one. Make sure you can note the new code down.</span>
          </p>
          {error && (
            <p role="alert" className="text-sm font-medium text-danger-soft">
              {error}
            </p>
          )}
        </div>
      )}
    </Sheet>
  );
};
