import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { ConfirmDialog, DateTime, Money, SkeletonBlock, useToast } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { BookingStatusBadge } from './shared';
import type { AdminCharger, Affected, OutOfServiceResult } from './types';

/**
 * "Set out of service". It first asks the server which future bookings this would break and shows them. With none,
 * one tap switches the charger off. With some, the only way forward is to cancel them with a full refund (or to close
 * the dialog and change nothing): a booking is never broken silently.
 */
export const OutOfServiceDialog: React.FC<{ charger: AdminCharger | null; onClose: () => void; onDone: () => void }> = ({ charger, onClose, onDone }) => {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ask the server what this would break every time a charger is picked.
  const key = charger ? `/api/admin/chargers/${charger.charger_id}/affected` : null;
  const query = useApiQuery(key, (signal) => apiFetch<Affected>(key as string, { signal }));
  const affected = query.data;
  const loadError = query.error;

  const count = affected?.bookings.length ?? 0;
  const confirm = async () => {
    if (!charger) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<OutOfServiceResult>(`/api/admin/chargers/${charger.charger_id}/out-of-service`, { method: 'POST', body: { cancel_bookings: count > 0 } });
      toast.success(
        result.cancelled > 0 ? `Charger ${charger.label} is out of service. ${result.cancelled} booking${result.cancelled === 1 ? '' : 's'} cancelled and refunded.` : `Charger ${charger.label} is out of service.`,
      );
      onDone();
      onClose();
    } catch (e) {
      // Someone booked it while this dialog was open: look again instead of cancelling what the admin never saw.
      if (e instanceof ApiError && e.code === 'HAS_FUTURE_BOOKINGS') {
        setError('A booking was made while you were looking. The list has been refreshed: check it and confirm again.');
        query.refresh();
      } else {
        setError(e instanceof Error ? e.message : 'Could not change the charger.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <ConfirmDialog
      open={charger !== null}
      title={charger ? `Set ${charger.label} out of service?` : ''}
      confirmLabel={count > 0 ? `Cancel ${count} booking${count === 1 ? '' : 's'} with full refund and switch off` : 'Set out of service'}
      danger
      busy={busy}
      error={error ?? loadError}
      onClose={onClose}
      onConfirm={() => void confirm()}
    >
      {!affected && !loadError && (
        <div role="status">
          <span className="sr-only">Checking bookings…</span>
          <SkeletonBlock className="h-20" />
        </div>
      )}
      {affected && affected.charging_now && (
        <p className="flex items-start gap-2 rounded-card border border-warning/40 bg-warning/10 p-3">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          Someone is charging on this charger right now. The session will be stopped and billed up to this moment.
        </p>
      )}
      {affected && count === 0 && <p>No future bookings are affected. Drivers will see the charger as out of service straight away.</p>}
      {affected && count > 0 && (
        <>
          <p>
            These <strong>{count}</strong> future booking{count === 1 ? '' : 's'} need this charger. Switching it off cancels {count === 1 ? 'it' : 'them'}: each driver gets a notice and
            everything they paid is refunded in full.
          </p>
          <ul className="max-h-60 divide-y divide-border overflow-y-auto rounded-card border border-border">
            {affected.bookings.map((b) => (
              <li key={b.booking_id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <div className="min-w-0">
                  <p className="font-medium"><DateTime value={b.start} /> – <DateTime value={b.end} format="time" /></p>
                  <p className="truncate text-xs text-muted">{b.user_email ?? 'Walk-in (no account)'}</p>
                </div>
                <div className="flex items-center gap-2">
                  <BookingStatusBadge status={b.status} />
                  <span className="text-xs text-muted">paid <Money value={b.fee_paid} /></span>
                </div>
              </li>
            ))}
          </ul>
          <p className="text-muted">Close this dialog to leave the charger as it is.</p>
        </>
      )}
    </ConfirmDialog>
  );
};
