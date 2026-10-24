import React, { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Clock, MapPin, Navigation, RefreshCw, Share2, Star, Zap } from 'lucide-react';
import { estimateEnergy, formatRelativeIST, istDateKey } from '@chargespot/shared';
import {
  ApproximateTag, availabilityFor, Badge, Button, buttonClasses, Card, ConnectorIcon, EmptyState, Money, SkeletonBlock, SkeletonLine,
  StatusBadge, TabPanel, Tabs, useToast,
} from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import { useChanged } from '../../lib/useChanged';
import { useRealtimeRefresh } from '../../lib/useRealtimeRefresh';
import { formatSlot } from '../bookings/format';
import type { Alternatives, BookingOut, InstantBookingOut, TicketState } from '../bookings/types';
import { useDues } from '../bookings/useBookings';
import { useVehicles } from '../profile/useVehicles';
import { AvailabilityGrid } from './AvailabilityGrid';
import { ChargeNowSheet } from './ChargeNowSheet';
import { directionsUrl } from './directions';
import { DuesBanner } from './DuesBanner';
import type { Selection } from './selection';
import { loadSelection, saveSelection } from './selectionStorage';
import { SlotTakenSheet } from './SlotTakenSheet';
import { SummaryBar } from './SummaryBar';
import type { ChargerDetail, StationDetail } from './types';
import { useAvailability, useStationDetail } from './useStationDetail';

const DAY_MS = 24 * 60 * 60 * 1000;
const DAYS_AHEAD = 6; // today plus six more
const BOOKING_FEE_INR = 199; // shown in the summary; the server decides the real amount

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

/** The day tabs (today and the next six days) and the picked blocks that were remembered for this station. */
function initialDays(stationId: string | undefined) {
  const now = new Date();
  const days = Array.from({ length: DAYS_AHEAD + 1 }, (_, i) => {
    const at = new Date(now.getTime() + i * DAY_MS);
    return { id: istDateKey(at), label: formatRelativeIST(at, { withTime: false, now }) };
  });
  const saved = stationId ? loadSelection(stationId) : null;
  const restored = saved && days.some((d) => d.id === saved.day) ? saved : null;
  return { days, day: restored?.day ?? days[0].id, selection: restored?.selection ?? null };
}

export const StationPage: React.FC = () => {
  const { stationId } = useParams();
  const navigate = useNavigate();
  const detail = useStationDetail(stationId);
  const dues = useDues();
  const { defaultVehicle } = useVehicles();

  const [initial] = useState(() => initialDays(stationId));
  const [day, setDay] = useState(initial.day);
  const [selection, setSelection] = useState<Selection | null>(initial.selection);
  const availability = useAvailability(stationId, day);

  // Live updates: when anything at this station changes, ask the API again (the message itself is never trusted).
  const refreshDetail = detail.refresh;
  const refreshAvailability = availability.refresh;
  useRealtimeRefresh(stationId ? [stationId] : [], () => {
    refreshDetail();
    refreshAvailability();
  });
  // Blocks that changed on their own flash briefly (switching day is not a change).
  const snapshot = useMemo(
    () => (availability.data ? new Map(availability.data.chargers.flatMap((c) => c.blocks.map((b): [string, string] => [`${c.charger_id}|${b.start}`, b.state]))) : null),
    [availability.data],
  );
  const changed = useChanged(snapshot, day);

  const [notice, setNotice] = useState<{ message: string; holdId?: string } | null>(null);
  const [holding, setHolding] = useState(false);
  const [alternatives, setAlternatives] = useState<Alternatives | null>(null);
  const [chargeNowId, setChargeNowId] = useState<string | null>(null);
  const [chargeNowBusy, setChargeNowBusy] = useState(false);
  const [chargeNowError, setChargeNowError] = useState<string | null>(null);

  // Back goes to wherever you came from (Explore keeps its map view); direct visits fall back to Explore.
  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate('/explore'));

  const backButton = (
    <Button variant="ghost" size="md" icon={<ArrowLeft className="size-4" aria-hidden="true" />} onClick={goBack}>
      Back
    </Button>
  );

  const changeSelection = (next: Selection | null, onDay = day) => {
    setSelection(next);
    setNotice(null);
    if (stationId) saveSelection(stationId, next ? { selection: next, day: onDay } : null);
  };

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
  const unpaid = dues.data && dues.data.count > 0 ? dues.data : null;

  // ---- what the driver has picked ----
  const pickedCharger = selection ? station.chargers.find((c) => c.charger_id === selection.chargerId) : undefined;
  const vehicle = pickedCharger && defaultVehicle && defaultVehicle.connector_type === pickedCharger.connector_type ? defaultVehicle : null;
  const estimate =
    pickedCharger && selection
      ? estimateEnergy({
          powerKw: pickedCharger.power_kw, pricePerKwh: pickedCharger.price_per_kwh, minutes: selection.blocks * 30, batteryKwh: vehicle?.battery_kwh,
        })
      : null;
  // A live update may have given part of the picked time to someone else.
  const pickRow = selection ? availability.data?.chargers.find((c) => c.charger_id === selection.chargerId) : undefined;
  const pickTaken =
    !!selection && !!pickRow &&
    pickRow.blocks.some((b) => b.start >= selection.startIso && b.end <= selection.endIso && b.state !== 'FREE');
  const vehicleNote = vehicle
    ? `Estimate uses your ${vehicle.nickname} (${vehicle.battery_kwh} kWh battery).`
    : defaultVehicle && pickedCharger
      ? `Your ${defaultVehicle.nickname} uses a different plug, so this estimate has no battery limit.`
      : undefined;

  // ---- holding a slot ----
  const hold = async (chargerId: string, startIso: string, blocks: number) => {
    setHolding(true);
    setNotice(null);
    try {
      const picked = station.chargers.find((c) => c.charger_id === chargerId);
      const carFits = defaultVehicle && picked && defaultVehicle.connector_type === picked.connector_type;
      const booking = await apiFetch<BookingOut>('/api/bookings', {
        method: 'POST',
        body: { charger_id: chargerId, start: startIso, blocks, vehicle_id: carFits ? defaultVehicle.vehicle_id : undefined },
      });
      setAlternatives(null);
      navigate(`/book/${booking.booking_id}`);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        setNotice({ message: 'Something went wrong. Please try again.' });
      } else if (error.code === 'SLOT_TAKEN') {
        setAlternatives((error.details?.alternatives as Alternatives | undefined) ?? { charger_id: chargerId, blocks, same_charger: [], other_chargers: [], stations: [] });
        availability.refresh(); // show what is free now
      } else if (error.code === 'ACTIVE_HOLD_EXISTS') {
        setNotice({ message: error.message, holdId: (error.details?.booking_id as string | undefined) });
      } else if (error.code === 'UNPAID_BILL') {
        dues.retry();
        setNotice({ message: error.message });
      } else {
        setNotice({ message: error.message });
      }
    } finally {
      setHolding(false);
    }
  };

  // ---- "Charge now" ----
  const chargeNowCharger = chargeNowId ? station.chargers.find((c) => c.charger_id === chargeNowId) : undefined;
  const chargeNow = async () => {
    if (!chargeNowCharger) return;
    setChargeNowBusy(true);
    setChargeNowError(null);
    try {
      const carFits = defaultVehicle && defaultVehicle.connector_type === chargeNowCharger.connector_type;
      const booking = await apiFetch<InstantBookingOut>('/api/bookings/instant', {
        method: 'POST',
        body: { charger_id: chargeNowCharger.charger_id, vehicle_id: carFits ? defaultVehicle.vehicle_id : undefined },
      });
      const state: TicketState = { otp: booking.otp };
      navigate(`/tickets/${booking.booking_id}`, { state });
    } catch (error) {
      if (error instanceof ApiError && error.code === 'UNPAID_BILL') dues.retry();
      setChargeNowError(error instanceof ApiError ? error.message : 'Something went wrong. Please try again.');
      detail.refresh(); // the charger may no longer be free
    } finally {
      setChargeNowBusy(false);
    }
  };

  const freeNow = new Set(station.chargers.filter((c) => c.free_now).map((c) => c.charger_id));
  // "Today" by the server's clock (the same one the grid uses for its "now" line).
  const isToday = availability.data ? availability.data.date === istDateKey(new Date(availability.data.now)) : false;

  return (
    <div className={`mx-auto max-w-4xl space-y-6 px-4 py-4 ${selection ? 'pb-44 md:pb-32' : ''}`}>
      {backButton}
      <Header station={station} />

      {unpaid && <DuesBanner dues={unpaid} />}

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
          <div>
            <h2 id="availability-heading" className="text-base font-bold">
              Pick a time
            </h2>
            <p className="text-sm text-muted">Tap a start block, then an end block (up to 4 blocks, 2 hours). On a computer you can also drag.</p>
          </div>
          <Tabs tabs={initial.days} value={day} onChange={setDay} label="Day" className="overflow-x-auto scroll-x-hidden" />
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
                <AvailabilityGrid
                  availability={availability.data}
                  selection={selection}
                  changed={changed}
                  onSelectionChange={(next) => (unpaid ? setNotice({ message: 'Pay your pending bill before booking again.' }) : changeSelection(next))}
                  onInvalid={(message) => setNotice({ message })}
                  rowAction={(charger) =>
                    isToday && freeNow.has(charger.charger_id) && !unpaid ? (
                      <Button
                        size="md"
                        variant="secondary"
                        className="mt-1"
                        icon={<Zap className="size-3.5" aria-hidden="true" />}
                        onClick={() => {
                          setChargeNowError(null);
                          setChargeNowId(charger.charger_id);
                        }}
                      >
                        Charge now
                      </Button>
                    ) : null
                  }
                />
              </div>
            ) : null}
          </TabPanel>

          <div aria-live="polite" className="min-h-6">
            {notice && (
              <p role="status" className="flex flex-wrap items-center gap-x-3 text-sm font-medium text-warning">
                {notice.message}
                {notice.holdId && (
                  <Link to={`/book/${notice.holdId}`} className="font-bold text-info underline-offset-2 hover:underline">
                    Go to your hold
                  </Link>
                )}
              </p>
            )}
          </div>
        </section>
      )}

      {selection && pickedCharger && (
        <SummaryBar
          chargerLabel={pickedCharger.label}
          slot={formatSlot(selection.startIso, selection.endIso)}
          fee={BOOKING_FEE_INR}
          estimate={estimate}
          vehicleNote={vehicleNote}
          loading={holding}
          disabledReason={unpaid ? 'Pay your pending bill before booking again.' : pickTaken ? 'Part of your pick was just taken. Choose again.' : undefined}
          onConfirm={() => void hold(selection.chargerId, selection.startIso, selection.blocks)}
          onClear={() => changeSelection(null)}
        />
      )}

      <SlotTakenSheet
        open={alternatives !== null}
        onClose={() => setAlternatives(null)}
        alternatives={alternatives}
        busy={holding}
        onBook={(chargerId, startIso, blocks) => {
          // Pick it first, so if this one is taken too the driver still sees where they were headed.
          const charger = station.chargers.find((c) => c.charger_id === chargerId);
          if (charger) changeSelection({ chargerId, startIso, endIso: new Date(new Date(startIso).getTime() + blocks * 30 * 60000).toISOString(), blocks });
          void hold(chargerId, startIso, blocks);
        }}
      />

      <ChargeNowSheet
        open={chargeNowCharger !== undefined}
        onClose={() => setChargeNowId(null)}
        stationName={station.name}
        chargerLabel={chargeNowCharger?.label ?? ''}
        busy={chargeNowBusy}
        error={chargeNowError}
        onConfirm={() => void chargeNow()}
      />
    </div>
  );
};
