import React, { useState } from 'react';
import { Check, ShieldAlert, Webhook } from 'lucide-react';
import { Badge, Button, Card, DateTime, EmptyState, useToast } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { PageHeader, QueryState } from './shared';
import type { Alert } from './types';

const KINDS: Record<string, { label: string; icon: React.ReactNode }> = {
  KIOSK_OTP_GUESSING: { label: 'Kiosk code guessing', icon: <ShieldAlert className="size-5 text-danger-soft" aria-hidden="true" /> },
  WEBHOOK_FAILED: { label: 'Payment webhook failed', icon: <Webhook className="size-5 text-warning" aria-hidden="true" /> },
};

/** Things the system noticed: someone guessing kiosk codes, a payment webhook that failed. Mark each as seen. */
export const AlertsPage: React.FC = () => {
  const toast = useToast();
  const [showSeen, setShowSeen] = useState(false);
  const key = `/api/admin/alerts?include_seen=${showSeen}`;
  const query = useApiQuery(key, (signal) => apiFetch<Alert[]>(key, { signal }));
  const [busy, setBusy] = useState<string | null>(null);

  const seen = async (alert: Alert) => {
    setBusy(alert.alert_id);
    try {
      await apiFetch(`/api/admin/alerts/${alert.alert_id}/seen`, { method: 'POST' });
      toast.success('Marked as seen');
      query.refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not mark it as seen.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader title="Alerts" subtitle="An alert that repeats within 10 minutes is shown once." />
      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" checked={showSeen} onChange={(e) => setShowSeen(e.target.checked)} className="size-5 accent-primary" />
        Show alerts I have already seen
      </label>
      <QueryState loading={query.loading} error={query.error} hasData={!!query.data} retry={query.retry} rows={3}>
        {query.data && query.data.length === 0 ? (
          <Card>
            <EmptyState icon={<Check className="size-7" />} title="Nothing needs your attention" text="Kiosk code-guessing and failed payment webhooks show up here." />
          </Card>
        ) : (
          <ul className="space-y-3">
            {(query.data ?? []).map((a) => (
              <li key={a.alert_id}>
                <Card className="flex flex-wrap items-start gap-3 p-4">
                  <span className="mt-0.5">{KINDS[a.kind]?.icon}</span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="flex flex-wrap items-center gap-2 font-bold">
                      {KINDS[a.kind]?.label ?? a.kind}
                      {a.resolved_at && <Badge>Seen</Badge>}
                    </p>
                    <p className="text-sm">{a.message}</p>
                    <p className="text-xs text-muted">
                      <DateTime value={a.created_at} />
                      {a.station_name ? ` · ${a.station_name}` : ''}
                    </p>
                    {Object.keys(a.details).length > 0 && (
                      <details className="text-xs text-muted">
                        <summary className="min-h-11 cursor-pointer py-2">Details</summary>
                        <pre className="overflow-x-auto whitespace-pre-wrap rounded-control bg-raised p-2">{JSON.stringify(a.details, null, 2)}</pre>
                      </details>
                    )}
                  </div>
                  {!a.resolved_at && (
                    <Button variant="secondary" loading={busy === a.alert_id} onClick={() => void seen(a)} icon={<Check className="size-4" aria-hidden="true" />}>
                      Mark as seen
                    </Button>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </>
  );
};
