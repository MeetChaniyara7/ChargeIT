import React, { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Clock, MapPin, Navigation, RefreshCw, Share2, Star } from 'lucide-react';
import { formatRelativeIST, istDateKey } from '@chargespot/shared';
import {
  ApproximateTag, availabilityFor, Badge, Button, buttonClasses, Card, ConnectorIcon, EmptyState, Money, SkeletonBlock, SkeletonLine,
  StatusBadge, TabPanel, Tabs, useToast,
} from '../../components/ui';
import { AvailabilityGrid } from './AvailabilityGrid';
import { directionsUrl } from './directions';
import type { ChargerDetail, StationDetail } from './types';
import { useAvailability, useStationDetail } from './useStationDetail';

const DAY_MS = 24 * 60 * 60 * 1000;
const DAYS_AHEAD = 6; // today plus six more

const chargerStatus = (charger: ChargerDetail) =>
  charger.status !== 'AVAILABLE' && charger.status !== 'IN_USE' && !charger.free_now ? ('offline' as const) : charger.free_now ? ('free' as const) : ('busy' as const);

const hoursBadge = (open: boolean | null | undefined) =>
  open === true ? <Badge tone="primary">Open now</Badge> : open === false ? <Badge tone="danger">Closed now</Badge> : <Badge>Hours unknown</Badge>;

const ChargerCard: React.FC<{ charger: ChargerDetail }> = ({ charger }) => {
  const status = chargerStatus(charger);
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-bold">{charger.label}</h3>
          <div className="mt-1 text-sm">
            <ConnectorIcon type={charger.connector_type} />
          </div>
        </div>
        <StatusBadge status={status} label={status === 'free' ? 'Free now' : status === 'busy' ? 'In use' : 'Out of service'} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-sm">
        <span className="num font-bold">{charger.power_kw ? `${charger.power_kw} kW` : 'Power unknown'}</span>
        <span className="font-bold">
          <Money value={charger.price_per_kwh} perKwh />
        </span>
        {charger.is_estimated && (
          <ApproximateTag
            reason={
              charger.estimated_fields?.length
                ? `Estimated from typical values: ${charger.estimated_fields.join(', ').replace(/_/g, ' ')}.`
                : undefined
            }
          />
        )}
      </div>
    </Card>
  );
};

const Header: React.FC<{ station: StationDetail }> = ({ station }) => {
  const toast = useToast();

  const share = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: station.name, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      toast.success('Link copied');
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return; // closed the share sheet
      toast.error("Couldn't share this page.");
    }
  };

  return (
    <header className="space-y-3">
      <div>
        <h1 className="text-xl font-bold md:text-2xl">{station.name}</h1>
        {station.operator_name && <p className="text-sm text-muted">{station.operator_name}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        {station.rating != null && (
          <span className="num inline-flex items-center gap-1.5" title={`${station.rating_count} ratings`}>
            <Star className="size-4 fill-warning text-warning" aria-hidden="true" />
            <span className="font-bold">{station.rating.toFixed(1)}</span>
            {station.rating_is_estimated && <ApproximateTag reason="This rating is a placeholder, not from real reviews." />}
          </span>
        )}
        {station.distance_km != null && (
          <span className="num font-bold text-info">
            {station.distance_km.toFixed(1)} km
            {station.eta_minutes_estimate ? ` · ~${Math.max(1, Math.round(station.eta_minutes_estimate))} min` : ''}
          </span>
        )}
        {station.has_estimated_data && <ApproximateTag reason="Some chargers, power or prices here are estimated from typical values for its operator." />}
      </div>

      <p className="flex items-start gap-1.5 text-sm text-muted">
        <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        {station.address || station.city || 'Address unknown'}
      </p>
      <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Clock className="size-4 shrink-0" aria-hidden="true" />
        <span>{station.opening_hours || 'Opening hours unknown'}</span>
        {hoursBadge(station.is_open_now)}
      </p>

      <div className="flex flex-wrap gap-2">
        <a href={directionsUrl(station)} target="_blank" rel="noopener noreferrer" className={buttonClasses()}>
          <Navigation className="size-4" aria-hidden="true" />
          Navigate
        </a>
        <Button variant="secondary" icon={<Share2 className="size-4" aria-hidden="true" />} onClick={() => void share()}>
          Share
        </Button>
      </div>
    </header>
  );
};

const GridSkeleton: React.FC = () => (
  <div role="status" className="space-y-2">
    <span className="sr-only">Loading availability…</span>
    <SkeletonBlock className="h-52" />
  </div>
);

export const StationPage: React.FC = () => {
  const { stationId } = useParams();
  const navigate = useNavigate();
  const detail = useStationDetail(stationId);

  // Day tabs: today and the next six days, as IST dates.
  const [days] = useState(() => {
    const now = new Date();
    return Array.from({ length: DAYS_AHEAD + 1 }, (_, i) => {
      const at = new Date(now.getTime() + i * DAY_MS);
      return { id: istDateKey(at), label: formatRelativeIST(at, { withTime: false, now }) };
    });
  });
  const [day, setDay] = useState(days[0].id);
  const availability = useAvailability(stationId, day);

  // Back goes to wherever you came from (Explore keeps its map view); direct visits fall back to Explore.
  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate('/explore'));

  const backButton = (
    <Button variant="ghost" size="sm" icon={<ArrowLeft className="size-4" aria-hidden="true" />} onClick={goBack}>
      Back
    </Button>
  );

  if (detail.loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-4" role="status">
        <span className="sr-only">Loading station…</span>
        <SkeletonLine className="h-6 w-40" />
        <SkeletonBlock className="h-40" />
        <SkeletonBlock className="h-56" />
      </div>
    );
  }

  if (detail.error && !detail.data) {
    const notFound = /not found|404/i.test(detail.error);
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-4">
        {backButton}
        <Card className="flex flex-col items-center gap-3 p-6 text-center">
          <AlertCircle className="size-9 text-danger" aria-hidden="true" />
          <h1 className="text-base font-bold">{notFound ? "We couldn't find that station" : "Couldn't load this station"}</h1>
          <p className="text-sm text-muted">{detail.error}</p>
          {notFound ? (
            <Link to="/explore" className={buttonClasses()}>
              Back to the map
            </Link>
          ) : (
            <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={detail.retry}>
              Try again
            </Button>
          )}
        </Card>
      </div>
    );
  }

  const station = detail.data;
  if (!station) return null;

  const summaryStatus = availabilityFor(station.charger_free, station.charger_total);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-4">
      {backButton}
      <Header station={station} />

      <section aria-labelledby="chargers-heading" className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 id="chargers-heading" className="text-base font-bold">
            Chargers
          </h2>
          <StatusBadge status={summaryStatus} label={station.charger_total > 0 ? `${station.charger_free}/${station.charger_total} free` : 'No chargers'} />
        </div>
        {station.chargers.length === 0 ? (
          <Card>
            <EmptyState icon={<MapPin className="size-7" />} title="No chargers listed" text="We don't have charger details for this station yet." />
          </Card>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {station.chargers.map((charger) => (
              <li key={charger.charger_id}>
                <ChargerCard charger={charger} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {station.chargers.length > 0 && (
        <section aria-labelledby="availability-heading" className="space-y-3">
          <h2 id="availability-heading" className="text-base font-bold">
            Availability
          </h2>
          <Tabs tabs={days} value={day} onChange={setDay} label="Day" className="overflow-x-auto scroll-x-hidden" />
          <TabPanel id={day} value={day}>
            {availability.loading ? (
              <GridSkeleton />
            ) : availability.error && !availability.data ? (
              <Card className="flex flex-col items-center gap-3 p-6 text-center">
                <AlertCircle className="size-7 text-danger" aria-hidden="true" />
                <p className="text-sm text-muted">{availability.error}</p>
                <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={availability.retry}>
                  Try again
                </Button>
              </Card>
            ) : availability.data ? (
              <div className={availability.refreshing ? 'opacity-60 transition-opacity' : undefined} aria-busy={availability.refreshing}>
                <AvailabilityGrid availability={availability.data} />
              </div>
            ) : null}
          </TabPanel>
        </section>
      )}
    </div>
  );
};
