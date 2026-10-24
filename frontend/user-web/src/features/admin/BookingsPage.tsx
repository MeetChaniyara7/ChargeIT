import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { History } from 'lucide-react';
import { Button, DataTable, DateTime, Field, Money, Pagination, Select, Sheet, SkeletonBlock, TextInput } from '../../components/ui';
import type { Column } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { BookingStatusBadge, PageHeader, QueryState } from './shared';
import { BOOKING_STATUS_OPTIONS, STATUS_LABELS } from './types';
import type { BookingEvent, BookingRow, BookingRows, StationRows } from './types';

const PAGE_SIZE = 20;

/** Who did what to a booking, in order: the audit trail from `booking_events`. */
const HistorySheet: React.FC<{ booking: BookingRow | null; onClose: () => void }> = ({ booking, onClose }) => {
  const key = booking ? `/api/admin/bookings/${booking.booking_id}/events` : null;
  const query = useApiQuery(key, (signal) => apiFetch<BookingEvent[]>(key as string, { signal }));
  return (
    <Sheet open={booking !== null} onClose={onClose} title="Booking history">
      {booking && (
        <p className="mb-3 text-sm text-muted">
          {booking.station_name} · {booking.charger_label} · <DateTime value={booking.start} />
        </p>
      )}
      <QueryState loading={query.loading} error={query.error} hasData={!!query.data} retry={query.retry} rows={2}>
        {query.data && query.data.length === 0 && <p className="text-sm text-muted">No history recorded.</p>}
        <ol className="space-y-3 border-l border-border pl-4">
          {(query.data ?? []).map((e) => (
            <li key={e.event_id} className="relative text-sm">
              <span className="absolute -left-[1.4rem] top-1.5 size-2.5 rounded-full bg-primary" aria-hidden="true" />
              <p className="font-bold">
                {e.from_status ? `${STATUS_LABELS[e.from_status] ?? e.from_status} → ` : 'Created as '}
                {STATUS_LABELS[e.to_status] ?? e.to_status}
              </p>
              <p className="text-xs text-muted">
                <DateTime value={e.created_at} /> · by {e.actor.toLowerCase()}
              </p>
              {e.reason && <p className="mt-0.5">{e.reason}</p>}
            </li>
          ))}
        </ol>
      </QueryState>
      {query.loading && <SkeletonBlock className="mt-2 h-10" />}
    </Sheet>
  );
};

/** Bookings with filters (station, status, date) and a history timeline for each. */
export const BookingsAdminPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const stationId = params.get('station') ?? '';
  const status = params.get('status') ?? '';
  const from = params.get('from') ?? '';
  const to = params.get('to') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const [history, setHistory] = useState<BookingRow | null>(null);

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
  const filter = (name: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => update({ [name]: e.target.value, page: null });

  const stations = useApiQuery('/api/admin/stations?sort=name&page_size=100', (signal) => apiFetch<StationRows>('/api/admin/stations?sort=name&page_size=100', { signal }));
  const key = `/api/admin/bookings?${new URLSearchParams({
    page: String(page), page_size: String(PAGE_SIZE),
    ...(stationId ? { station_id: stationId } : {}), ...(status ? { status } : {}), ...(from ? { date_from: from } : {}), ...(to ? { date_to: to } : {}),
  })}`;
  const query = useApiQuery(key, (signal) => apiFetch<BookingRows>(key, { signal }));
  const data = query.data;

  const columns: Column<BookingRow>[] = [
    { id: 'start', header: 'Slot', cell: (r) => (<span className="whitespace-nowrap"><DateTime value={r.start} /> – <DateTime value={r.end} format="time" /></span>) },
    { id: 'station', header: 'Station', cell: (r) => <span className="block max-w-[14rem] truncate font-medium" title={r.station_name}>{r.station_name}</span> },
    { id: 'charger', header: 'Charger', cell: (r) => r.charger_label },
    { id: 'status', header: 'Status', cell: (r) => <BookingStatusBadge status={r.status} /> },
    { id: 'source', header: 'Type', cell: (r) => ({ APP: 'Booked', INSTANT: 'Charge now', WALK_IN: 'Walk-in' } as Record<string, string>)[r.source] ?? r.source },
    { id: 'user', header: 'Driver', cell: (r) => (r.user_email ? <span className="block max-w-[14rem] truncate" title={r.user_email}>{r.user_email}</span> : <span className="text-muted">no account</span>) },
    { id: 'fee', header: 'Fee', align: 'right', cell: (r) => <Money value={r.booking_fee} /> },
    { id: 'refund', header: 'Refunded', align: 'right', cell: (r) => (r.refund_amount > 0 ? <Money value={r.refund_amount} /> : <span className="text-muted">—</span>) },
    {
      id: 'history', header: 'History', align: 'right',
      cell: (r) => (
        <Button size="md" variant="ghost" icon={<History className="size-4" aria-hidden="true" />} onClick={() => setHistory(r)} aria-label={`Show the history of the booking at ${r.station_name}, ${r.charger_label}`}>
          History
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Bookings" subtitle="By the day the slot starts (India time), newest first." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Station">
          {(p) => (
            <Select value={stationId} onChange={filter('station')} {...p}>
              <option value="">All stations</option>
              {(stations.data?.items ?? []).map((s) => (
                <option key={s.station_id} value={s.station_id}>{s.name}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Status">
          {(p) => (
            <Select value={status} onChange={filter('status')} {...p}>
              <option value="">Any status</option>
              {BOOKING_STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="From">{(p) => <TextInput type="date" value={from} max={to || undefined} onChange={filter('from')} {...p} />}</Field>
        <Field label="To">{(p) => <TextInput type="date" value={to} min={from || undefined} onChange={filter('to')} {...p} />}</Field>
      </div>
      <QueryState loading={query.loading} error={query.error} hasData={!!data} retry={query.retry} rows={5}>
        {data && (
          <div className="space-y-3" aria-busy={query.refreshing}>
            <DataTable
              caption="Bookings"
              columns={columns}
              rows={data.items}
              rowKey={(r) => r.booking_id}
              empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">No bookings match these filters.</p>}
            />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(n) => update({ page: String(n) })} />
          </div>
        )}
      </QueryState>
      <HistorySheet booking={history} onClose={() => setHistory(null)} />
    </>
  );
};
