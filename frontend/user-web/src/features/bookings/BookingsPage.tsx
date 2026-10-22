import React, { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertCircle, RefreshCw, Ticket, Wallet } from 'lucide-react';
import { buttonClasses, Button, Card, DateTime, EmptyState, Money, SkeletonBlock, TabPanel, Tabs } from '../../components/ui';
import { useRealtimeRefresh } from '../../lib/useRealtimeRefresh';
import { PayBillButton } from '../charging/PayBillButton';
import { BookingCard } from './BookingCard';
import { CancelSheet, NewCodeSheet } from './BookingSheets';
import type { BookingOut, BookingScope } from './types';
import { useNoticeToasts } from './useNoticeToasts';
import { useDues, useMyBookings } from './useBookings';

type Tab = BookingScope | 'due';
const TAB_IDS: Tab[] = ['upcoming', 'past', 'due'];

const BookingList: React.FC<{
  scope: BookingScope;
  onCancel: (booking: BookingOut) => void;
  onNewCode: (booking: BookingOut) => void;
  refreshKey: number;
}> = ({ scope, onCancel, onNewCode, refreshKey }) => {
  const query = useMyBookings(scope);
  // Live updates for the stations of upcoming bookings (a booking moved, a no-show, charging started...),
  // and a toast when a notice appears while this page is open.
  const stationIds = useMemo(() => (scope === 'upcoming' ? (query.data ?? []).map((b) => b.station.station_id).slice(0, 10) : []), [scope, query.data]);
  useRealtimeRefresh(stationIds, query.refresh);
  useNoticeToasts(query.data);
  // After a cancellation the parent bumps refreshKey; ask the server again.
  const [seenKey, setSeenKey] = useState(refreshKey);
  if (seenKey !== refreshKey) {
    setSeenKey(refreshKey);
    query.retry();
  }

  if (query.loading) {
    return (
      <div role="status" className="space-y-3">
        <span className="sr-only">Loading your bookings…</span>
        <SkeletonBlock className="h-44" />
        <SkeletonBlock className="h-44" />
      </div>
    );
  }
  if (query.error && !query.data) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <AlertCircle className="size-9 text-danger" aria-hidden="true" />
        <h2 className="text-base font-bold">Couldn&apos;t load your bookings</h2>
        <p className="text-sm text-muted">{query.error}</p>
        <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={query.retry}>
          Try again
        </Button>
      </Card>
    );
  }
  const bookings = query.data ?? [];
  if (bookings.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<Ticket className="size-7" />}
          title={scope === 'upcoming' ? 'No upcoming bookings' : 'No past bookings yet'}
          text={scope === 'upcoming' ? 'Pick a charger and a time, and your ticket will show up here.' : 'Finished, cancelled and expired bookings appear here.'}
          action={
            scope === 'upcoming' ? (
              <Link to="/explore" className={buttonClasses()}>
                Find a charger
              </Link>
            ) : undefined
          }
        />
      </Card>
    );
  }
  return (
    <ul className="space-y-3">
      {query.error && (
        <li role="alert" className="text-xs text-danger-soft">
          Couldn&apos;t refresh. Showing earlier results.
        </li>
      )}
      {bookings.map((booking) => (
        <li key={booking.booking_id}>
          <BookingCard booking={booking} onCancel={onCancel} onNewCode={onNewCode} />
        </li>
      ))}
    </ul>
  );
};

const DueList: React.FC<{ dues: ReturnType<typeof useDues> }> = ({ dues }) => {
  if (dues.loading) {
    return (
      <div role="status">
        <span className="sr-only">Loading your bills…</span>
        <SkeletonBlock className="h-28" />
      </div>
    );
  }
  if (dues.error && !dues.data) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <AlertCircle className="size-9 text-danger" aria-hidden="true" />
        <p className="text-sm text-muted">{dues.error}</p>
        <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={dues.retry}>
          Try again
        </Button>
      </Card>
    );
  }
  const data = dues.data;
  if (!data || data.count === 0) {
    return (
      <Card>
        <EmptyState icon={<Wallet className="size-7" />} title="Nothing to pay" text="Energy bills appear here after a charging session, until you pay them." />
      </Card>
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">You can book again once these are paid.</p>
      <ul className="space-y-3">
        {data.items.map((item) => (
          <li key={item.session_id}>
            <Card className="space-y-3 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-base font-bold">{item.station_name ?? 'Charging session'}</p>
                  {item.ended_at && <p className="text-sm text-muted"><DateTime value={item.ended_at} /></p>}
                </div>
                <Money value={item.amount} className="text-xl font-bold" />
              </div>
              <div className="flex flex-wrap items-start gap-2">
                <div className="min-w-40 flex-1">
                  <PayBillButton sessionId={item.session_id} amount={item.amount} size="md" onPaid={dues.refresh} />
                </div>
                <Link to={`/receipts/session/${item.session_id}`} className={buttonClasses({ variant: 'secondary' })}>
                  Details
                </Link>
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
};

export const BookingsPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab') as Tab | null;
  const tab: Tab = requested && TAB_IDS.includes(requested) ? requested : 'upcoming';
  const dues = useDues();

  const [cancelling, setCancelling] = useState<BookingOut | null>(null);
  const [newCodeFor, setNewCodeFor] = useState<BookingOut | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="mx-auto max-w-2xl space-y-4 px-4 py-6">
      <h1 className="text-display font-bold">Bookings</h1>
      <Tabs
        label="Booking status"
        value={tab}
        onChange={(id) => setParams(id === 'upcoming' ? {} : { tab: id }, { replace: true })}
        tabs={[
          { id: 'upcoming', label: 'Upcoming' },
          { id: 'past', label: 'Past' },
          { id: 'due', label: 'Payment due', count: dues.data?.count },
        ]}
        className="overflow-x-auto scroll-x-hidden"
      />
      <TabPanel id="upcoming" value={tab}>
        <BookingList scope="upcoming" onCancel={setCancelling} onNewCode={setNewCodeFor} refreshKey={refreshKey} />
      </TabPanel>
      <TabPanel id="past" value={tab}>
        <BookingList scope="past" onCancel={setCancelling} onNewCode={setNewCodeFor} refreshKey={refreshKey} />
      </TabPanel>
      <TabPanel id="due" value={tab}>
        <DueList dues={dues} />
      </TabPanel>

      <CancelSheet booking={cancelling} onClose={() => setCancelling(null)} onCancelled={() => setRefreshKey((n) => n + 1)} />
      <NewCodeSheet booking={newCodeFor} onClose={() => setNewCodeFor(null)} />
    </div>
  );
};
