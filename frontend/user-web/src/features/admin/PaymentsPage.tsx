import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { Badge, DataTable, DateTime, Field, Money, Pagination, Select } from '../../components/ui';
import type { BadgeTone, Column } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { PageHeader, QueryState } from './shared';
import type { PaymentRow, PaymentRows } from './types';

const PAGE_SIZE = 20;
const PURPOSES: Record<string, string> = { BOOKING_FEE: 'Booking fee', ENERGY: 'Energy bill', WALKIN_PREPAID: 'Walk-in' };
const STATUSES: Record<string, { label: string; tone: BadgeTone }> = {
  CREATED: { label: 'Waiting', tone: 'warning' },
  CAPTURED: { label: 'Paid', tone: 'primary' },
  PARTIALLY_REFUNDED: { label: 'Part refunded', tone: 'info' },
  REFUNDED: { label: 'Refunded', tone: 'neutral' },
  FAILED: { label: 'Failed', tone: 'danger' },
};

/** Every payment with its refunds. Test mode: refunds are recorded, no real money moves. */
export const PaymentsPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const purpose = params.get('purpose') ?? '';
  const status = params.get('status') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const update = (changes: Record<string, string | null>) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [k, v] of Object.entries(changes)) {
          if (v === null || v === '') next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: true },
    );
  const key = `/api/admin/payments?${new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), ...(purpose ? { purpose } : {}), ...(status ? { status } : {}) })}`;
  const query = useApiQuery(key, (signal) => apiFetch<PaymentRows>(key, { signal }));
  const data = query.data;

  const columns: Column<PaymentRow>[] = [
    { id: 'when', header: 'When', cell: (p) => <span className="whitespace-nowrap"><DateTime value={p.created_at} /></span> },
    {
      id: 'purpose', header: 'For',
      cell: (p) => (
        <div>
          <p>{PURPOSES[p.purpose] ?? p.purpose}</p>
          {p.provider_payment_id && <p className="font-mono text-xs text-muted">{p.provider_payment_id}</p>}
        </div>
      ),
    },
    { id: 'station', header: 'Station', cell: (p) => <span className="block max-w-[14rem] truncate" title={p.station_name ?? undefined}>{p.station_name ?? '—'}</span> },
    { id: 'driver', header: 'Driver', cell: (p) => (p.user_email ? <span className="block max-w-[14rem] truncate" title={p.user_email}>{p.user_email}</span> : <span className="text-muted">walk-in, no account</span>) },
    { id: 'amount', header: 'Amount', align: 'right', cell: (p) => <Money value={p.amount} className="font-bold" /> },
    { id: 'refunded', header: 'Refunded', align: 'right', cell: (p) => (p.refunded_amount > 0 ? <Money value={p.refunded_amount} /> : <span className="text-muted">—</span>) },
    { id: 'status', header: 'Status', cell: (p) => <Badge tone={STATUSES[p.status]?.tone ?? 'neutral'}>{STATUSES[p.status]?.label ?? p.status}</Badge> },
  ];

  return (
    <>
      <PageHeader title="Payments" subtitle="Test mode: payments and refunds are recorded, but no real money moves." />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="For" className="w-48">
          {(p) => (
            <Select value={purpose} onChange={(e) => update({ purpose: e.target.value, page: null })} {...p}>
              <option value="">Everything</option>
              {Object.entries(PURPOSES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Status" className="w-48">
          {(p) => (
            <Select value={status} onChange={(e) => update({ status: e.target.value, page: null })} {...p}>
              <option value="">Any status</option>
              {Object.entries(STATUSES).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </Select>
          )}
        </Field>
        {data && (
          <p className="pb-3 text-sm text-muted">
            Matching: <Money value={data.amount_total} className="font-bold text-fg" /> paid, <Money value={data.refunded_total} className="font-bold text-fg" /> refunded
          </p>
        )}
      </div>
      <QueryState loading={query.loading} error={query.error} hasData={!!data} retry={query.retry} rows={5}>
        {data && (
          <div className="space-y-3" aria-busy={query.refreshing}>
            <DataTable
              caption="Payments"
              columns={columns}
              rows={data.items}
              rowKey={(p) => p.payment_id}
              empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">No payments match these filters.</p>}
            />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(n) => update({ page: String(n) })} />
          </div>
        )}
      </QueryState>
    </>
  );
};
