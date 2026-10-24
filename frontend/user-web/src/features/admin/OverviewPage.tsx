import React, { useState } from 'react';
import { BarList, Card, ColumnChart, DataTable, Field, Money, StatTile, TextInput } from '../../components/ui';
import type { Column } from '../../components/ui';
import { formatDateIST } from '@chargespot/shared';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { PageHeader, QueryState } from './shared';
import { STATUS_LABELS } from './types';
import type { Overview, Report } from './types';

/** An India-time calendar day as YYYY-MM-DD, n days from today. */
function dayOffset(n: number): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date(Date.now() + n * 86_400_000));
}

const Reports: React.FC = () => {
  const [from, setFrom] = useState(() => dayOffset(-29));
  const [to, setTo] = useState(() => dayOffset(0));
  const key = `/api/admin/reports?date_from=${from}&date_to=${to}`;
  const query = useApiQuery(from && to ? key : null, (signal) => apiFetch<Report>(key, { signal }));
  const report = query.data;
  const settlement: Column<Report['settlement'][number]>[] = [
    { id: 'operator', header: 'Operator', cell: (r) => r.operator_name },
    { id: 'sessions', header: 'Payments', align: 'right', cell: (r) => <span className="num">{r.sessions}</span> },
    { id: 'revenue', header: 'Energy revenue', align: 'right', cell: (r) => <Money value={r.energy_revenue} className="font-bold" /> },
  ];
  const statuses: Column<Report['bookings_by_status'][number]>[] = [
    { id: 'status', header: 'Status', cell: (r) => STATUS_LABELS[r.status] ?? r.status },
    { id: 'count', header: 'Bookings', align: 'right', cell: (r) => <span className="num">{r.count}</span> },
  ];
  return (
    <section aria-labelledby="reports-heading" className="space-y-4">
      <h2 id="reports-heading" className="text-xl font-bold">
        Reports
      </h2>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="From" className="w-44">{(p) => <TextInput type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} {...p} />}</Field>
        <Field label="To" className="w-44">{(p) => <TextInput type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} {...p} />}</Field>
      </div>
      <QueryState loading={query.loading} error={query.error} hasData={!!report} retry={query.retry}>
        {report && (
          <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
            <div className="space-y-2">
              <h3 className="text-base font-bold">Bookings by status</h3>
              <DataTable
                caption="Bookings by status"
                columns={statuses}
                rows={report.bookings_by_status}
                rowKey={(r) => r.status}
                empty={<p className="rounded-card border border-border p-4 text-sm text-muted">No bookings in these days.</p>}
              />
              <p className="text-sm text-muted">
                No-shows in these days: <span className="num font-bold text-fg">{report.no_shows}</span>
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="text-base font-bold">Revenue</h3>
              <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 rounded-card border border-border bg-surface p-4 text-sm">
                <dt className="text-muted">Booking fees (net)</dt>
                <dd className="text-right"><Money value={report.revenue.booking_fees} /></dd>
                <dt className="text-muted">Energy bills (net)</dt>
                <dd className="text-right"><Money value={report.revenue.energy} /></dd>
                <dt className="text-muted">Walk-ins (net)</dt>
                <dd className="text-right"><Money value={report.revenue.walk_ins} /></dd>
                <dt className="text-muted">Refunds recorded</dt>
                <dd className="text-right"><Money value={report.revenue.refunds} /></dd>
              </dl>
              <p className="text-xs text-muted">Test mode: refunds are recorded; no real money moves.</p>
            </div>
            <div className="space-y-2 lg:col-span-2">
              <h3 className="text-base font-bold">Operator settlement</h3>
              <p className="text-xs text-muted">What each operator earned from energy (paid bills and walk-in sessions), after refunds.</p>
              <DataTable
                caption="Energy revenue per operator"
                columns={settlement}
                rows={report.settlement}
                rowKey={(r) => r.operator_name}
                empty={<p className="rounded-card border border-border p-4 text-sm text-muted">No energy payments in these days.</p>}
              />
            </div>
          </div>
        )}
      </QueryState>
    </section>
  );
};

/** Today's numbers, two simple charts, and the reports. */
export const OverviewPage: React.FC = () => {
  const query = useApiQuery('/api/admin/overview', (signal) => apiFetch<Overview>('/api/admin/overview', { signal }));
  const o = query.data;
  return (
    <>
      <PageHeader title="Overview" subtitle="Everything here is read from the live database." />
      <QueryState loading={query.loading} error={query.error} hasData={!!o} retry={query.retry} rows={4}>
        {o && (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 [&>*]:min-w-0">
              <StatTile label="Bookings today" value={o.today_bookings} hint="slots starting today" />
              <StatTile label="Charging now" value={o.active_sessions} hint="sessions running" />
              <StatTile label="No-shows this week" value={o.no_shows_week} hint="last 7 days" />
              <StatTile label="Open alerts" value={o.open_alerts} hint="not yet seen" />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 [&>*]:min-w-0">
              <StatTile label="Booking fees" value={<Money value={o.revenue.booking_fees} />} hint={`last ${o.revenue_days} days, net of refunds`} />
              <StatTile label="Energy bills" value={<Money value={o.revenue.energy} />} hint={`last ${o.revenue_days} days, net of refunds`} />
              <StatTile label="Walk-ins" value={<Money value={o.revenue.walk_ins} />} hint={`last ${o.revenue_days} days, net of refunds`} />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="min-w-0 space-y-2 p-4">
                <h2 className="text-base font-bold">Bookings per day</h2>
                <p className="text-xs text-muted">The last 14 days, by the day the slot starts (India time).</p>
                <ColumnChart
                  label="Bookings per day, last 14 days"
                  data={o.bookings_per_day.map((d) => ({
                    label: formatDateIST(`${d.day}T12:00:00+05:30`).replace(/^\w+ /, ''),
                    title: formatDateIST(`${d.day}T12:00:00+05:30`),
                    value: d.count,
                  }))}
                />
              </Card>
              <Card className="min-w-0 space-y-2 p-4">
                <h2 className="text-base font-bold">No-shows per station</h2>
                <p className="text-xs text-muted">The last 30 days: the stations with the most missed bookings.</p>
                {o.no_shows_by_station.length === 0 ? (
                  <p className="py-6 text-sm text-muted">No no-shows in the last 30 days.</p>
                ) : (
                  <BarList data={o.no_shows_by_station.map((s) => ({ label: s.station_name, value: s.count }))} />
                )}
              </Card>
            </div>
          </>
        )}
      </QueryState>
      <Reports />
    </>
  );
};
