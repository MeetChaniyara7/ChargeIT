import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { ApproximateTag, Badge, Button, Card, SkeletonBlock } from '../../components/ui';
import type { BadgeTone } from '../../components/ui';
import { STATUS_LABELS } from './types';

/** Where a station or charger record came from. Generated data says so. */
export const SourceBadge: React.FC<{ source: string }> = ({ source }) => {
  if (source === 'synthetic') return <ApproximateTag />;
  const names: Record<string, string> = { manual: 'Manual', ocm: 'Open Charge Map', osm: 'OpenStreetMap' };
  return <Badge tone={source === 'manual' ? 'primary' : 'info'}>{names[source] ?? source}</Badge>;
};

const BOOKING_TONES: Record<string, BadgeTone> = {
  HELD: 'warning', CONFIRMED: 'info', ACTIVE: 'primary', COMPLETED: 'neutral', EXPIRED: 'neutral', CANCELLED: 'neutral', NO_SHOW: 'danger',
};

/** A booking status as a word with a colour. */
export const BookingStatusBadge: React.FC<{ status: string }> = ({ status }) => (
  <Badge tone={BOOKING_TONES[status] ?? 'neutral'}>{STATUS_LABELS[status] ?? status}</Badge>
);

const CHARGER_TONES: Record<string, BadgeTone> = {
  AVAILABLE: 'primary', RESERVED: 'warning', CHARGING: 'info', FAULTED: 'danger', OUT_OF_SERVICE: 'danger',
};
const CHARGER_LABELS: Record<string, string> = {
  AVAILABLE: 'Available', RESERVED: 'Reserved', CHARGING: 'Charging', FAULTED: 'Faulted', OUT_OF_SERVICE: 'Out of service',
};

export const ChargerStatusBadge: React.FC<{ status: string }> = ({ status }) => (
  <Badge tone={CHARGER_TONES[status] ?? 'neutral'}>{CHARGER_LABELS[status] ?? status}</Badge>
);

/** The same loading and error patterns as the rest of the app, for any admin query. */
export const QueryState: React.FC<{ loading: boolean; error: string | null; hasData: boolean; retry: () => void; children: React.ReactNode; rows?: number }> = ({
  loading, error, hasData, retry, children, rows = 3,
}) => {
  if (loading) {
    return (
      <div role="status" className="space-y-3">
        <span className="sr-only">Loading…</span>
        {Array.from({ length: rows }, (_, i) => (
          <SkeletonBlock key={i} className="h-16" />
        ))}
      </div>
    );
  }
  if (error && !hasData) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <AlertCircle className="size-9 text-danger" aria-hidden="true" />
        <p className="text-sm text-muted">{error}</p>
        <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={retry}>
          Try again
        </Button>
      </Card>
    );
  }
  return <>{children}</>;
};

/** A page heading with an optional action on the right. */
export const PageHeader: React.FC<{ title: string; action?: React.ReactNode; subtitle?: string }> = ({ title, action, subtitle }) => (
  <div className="flex flex-wrap items-start justify-between gap-3">
    <div>
      <h1 className="text-display font-bold">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
    </div>
    {action}
  </div>
);
