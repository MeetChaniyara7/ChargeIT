import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { DataTable, DateTime, Pagination } from '../../components/ui';
import type { Column } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { PageHeader, QueryState } from './shared';
import type { ActivityRow, ActivityRows } from './types';

const PAGE_SIZE = 25;

const ACTIONS: Record<string, string> = {
  USER_ROLE_CHANGED: 'Changed a role',
  KIOSK_KEY_CREATED: 'Created a kiosk key',
  KIOSK_KEY_ROTATED: 'Replaced a kiosk key',
  KIOSK_KEY_REVOKED: 'Revoked a kiosk key',
  KIOSK_RENAMED: 'Renamed a kiosk',
  CHARGER_OUT_OF_SERVICE: 'Took a charger out of service',
  CHARGER_RESTORED: 'Put a charger back in service',
  CHARGER_ADDED: 'Added a charger',
  CHARGER_EDITED: 'Edited a charger',
  STATION_EDITED: 'Edited a station',
  OPERATOR_CREATED: 'Added an operator',
  OPERATOR_EDITED: 'Edited an operator',
  OPERATOR_DELETED: 'Deleted an operator',
};

/** Details in words, for the few actions where they matter. */
function detailText(row: ActivityRow): string {
  const d = row.details as Record<string, unknown>;
  if (row.action === 'USER_ROLE_CHANGED') return `${d.from === 'ADMIN' ? 'Admin' : 'Driver'} to ${d.to === 'ADMIN' ? 'admin' : 'driver'}`;
  if (row.action === 'CHARGER_OUT_OF_SERVICE') {
    const cancelled = Number(d.cancelled ?? 0);
    return cancelled > 0 ? `${cancelled} booking${cancelled === 1 ? '' : 's'} cancelled, ₹${Number(d.refunded ?? 0)} refunded${d.session_ended ? ', a running session was stopped' : ''}` : d.session_ended ? 'A running session was stopped' : '';
  }
  if (row.action === 'KIOSK_KEY_ROTATED' || row.action === 'KIOSK_KEY_REVOKED' || row.action === 'KIOSK_KEY_CREATED') {
    const prefix = (d.new_prefix ?? d.key_prefix) as string | undefined;
    return prefix ? `key starts ks_${prefix}_` : '';
  }
  const keys = Object.keys(d);
  return keys.length ? `changed: ${keys.join(', ')}` : '';
}

/** What admins changed, who did it and when. The jury can be shown this next to a booking history. */
export const ActivityPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get('page')) || 1);
  const key = `/api/admin/activity?page=${page}&page_size=${PAGE_SIZE}`;
  const query = useApiQuery(key, (signal) => apiFetch<ActivityRows>(key, { signal }));
  const data = query.data;
  const columns: Column<ActivityRow>[] = [
    { id: 'when', header: 'When', cell: (r) => <span className="whitespace-nowrap"><DateTime value={r.created_at} /></span> },
    { id: 'admin', header: 'Admin', cell: (r) => r.admin_email },
    { id: 'action', header: 'Action', cell: (r) => <span className="font-medium">{ACTIONS[r.action] ?? r.action}</span> },
    { id: 'target', header: 'On', cell: (r) => r.target ?? <span className="text-muted">—</span> },
    { id: 'details', header: 'Details', cell: (r) => detailText(r) || <span className="text-muted">—</span> },
  ];
  return (
    <>
      <PageHeader title="Activity log" subtitle="Every change made through the admin pages, newest first." />
      <QueryState loading={query.loading} error={query.error} hasData={!!data} retry={query.retry} rows={5}>
        {data && (
          <div className="space-y-3">
            <DataTable
              caption="Admin activity"
              columns={columns}
              rows={data.items}
              rowKey={(r) => String(r.action_id)}
              empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">Nothing has been changed yet.</p>}
            />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(n) => setParams({ page: String(n) }, { replace: true })} />
          </div>
        )}
      </QueryState>
    </>
  );
};
