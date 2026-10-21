import React, { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertCircle, AlertTriangle, ArrowLeft, BatteryCharging, MapPin, RefreshCw, Square } from 'lucide-react';
import { formatTimeIST } from '@chargespot/shared';
import { Button, buttonClasses, Card, EmptyState, Money, Sheet, SkeletonBlock, SkeletonLine, useToast } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import { useAnimatedNumber } from '../../lib/useAnimatedNumber';
import { formatDuration, useSecondsLeft } from '../../lib/useSecondsLeft';
import { useActiveSession } from './activeSessionContext';
import { BatteryRing } from './BatteryRing';
import { SessionSummary } from './SessionSummary';
import { useLiveSession } from './useLiveSession';
import type { LiveSession } from './types';

const Stat: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="rounded-card border border-border bg-surface p-3 text-center">
    <dd className="num text-xl font-bold">{children}</dd>
    <dt className="mt-0.5 text-xs text-muted">{label}</dt>
  </div>
);

/** What the driver sees while charging: the ring, the numbers, a warning before an automatic stop, and Stop. */
export const LiveChargingPage: React.FC = () => {
  const { sessionId } = useParams();
  const toast = useToast();
  const { refresh: refreshActive } = useActiveSession();
  const query = useLiveSession(sessionId);
  const data = query.data;
  const session: LiveSession | undefined = data?.session;

  // The numbers glide to each new value from the API instead of jumping.
  const percent = useAnimatedNumber(session?.battery_percent ?? 0);
  const energy = useAnimatedNumber(session?.energy_kwh ?? 0);
  const cost = useAnimatedNumber(session?.cost_so_far ?? 0);
  const secondsLeft = useSecondsLeft(session?.status === 'RUNNING' ? session.seconds_left : null, data?.receivedAt);

  const [confirmingStop, setConfirmingStop] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);

  // Tell the driver when a session that was running ends by itself (the slot ended, an unplug, a fault).
  const wasRunning = useRef(false);
  const status = session?.status;
  const endReason = session?.end_reason;
  useEffect(() => {
    if (status === 'RUNNING') wasRunning.current = true;
    else if (status === 'ENDED' && wasRunning.current) {
      wasRunning.current = false;
      if (endReason && endReason !== 'USER_STOP') toast.info('Charging has stopped.');
      refreshActive();
    }
  }, [status, endReason, toast, refreshActive]);

  const stop = async () => {
    if (!sessionId) return;
    setStopping(true);
    setStopError(null);
    try {
      await apiFetch<LiveSession>(`/api/me/sessions/${sessionId}/stop`, { method: 'POST' });
      setConfirmingStop(false);
      query.refresh();
      refreshActive();
    } catch (error) {
      setStopError(error instanceof ApiError ? error.message : 'Could not stop charging. Please try again.');
    } finally {
      setStopping(false);
    }
  };

  if (query.loading) {
    return (
      <div className="mx-auto max-w-md space-y-5 px-4 py-6" role="status">
        <span className="sr-only">Loading your charging session…</span>
        <SkeletonLine className="h-6 w-2/3" />
        <SkeletonBlock className="mx-auto aspect-square w-full max-w-72 rounded-full" />
        <SkeletonBlock className="h-20" />
      </div>
    );
  }

  if (query.error && !session) {
    const notFound = /not found|404/i.test(query.error);
    return (
      <div className="mx-auto max-w-md px-4 py-6">
        <Card>
          {notFound ? (
            <EmptyState
              icon={<BatteryCharging className="size-7" />}
              title="Session not found"
              text="We couldn't find that charging session. It may belong to another account."
              action={
                <Link to="/bookings" className={buttonClasses()}>
                  My bookings
                </Link>
              }
            />
          ) : (
            <div className="flex flex-col items-center gap-3 p-6 text-center">
              <AlertCircle className="size-9 text-danger" aria-hidden="true" />
              <h1 className="text-base font-bold">Couldn&apos;t load this session</h1>
              <p className="text-sm text-muted">{query.error}</p>
              <Button icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={query.retry}>
                Try again
              </Button>
            </div>
          )}
        </Card>
      </div>
    );
  }
  if (!session) return null;

  const running = session.status === 'RUNNING';

  return (
    <div className="mx-auto max-w-md space-y-5 px-4 py-6">
      <Link to="/charging" className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-info">
        <ArrowLeft className="size-4" aria-hidden="true" />
        Charging
      </Link>

      <div className="text-center">
        <h1 className="text-xl font-bold">{running ? 'Charging now' : 'Charging finished'}</h1>
        <p className="mt-0.5 flex items-center justify-center gap-1.5 text-sm text-muted">
          <MapPin className="size-4 shrink-0" aria-hidden="true" />
          {session.station.name} · {session.charger.label}
          {session.charger.power_kw ? ` · ${session.charger.power_kw} kW` : ''}
        </p>
      </div>

      {running && session.stop_warning && session.planned_stop_at && (
        <div role="alert" className="flex items-start gap-3 rounded-card border border-warning/50 bg-warning/10 p-3 text-sm">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden="true" />
          <p>
            <span className="font-bold">Stops at {formatTimeIST(session.planned_stop_at)}</span>
            {session.next_booking_waiting ? ', next booking waiting.' : ', when your booked time ends.'} Stop earlier below if you are done.
          </p>
        </div>
      )}

      <BatteryRing percent={percent} running={running} />

      <dl className="grid grid-cols-3 gap-2">
        <Stat label="Energy">
          {energy.toFixed(1)}
          <span className="text-sm font-medium text-muted"> kWh</span>
        </Stat>
        <Stat label={running ? 'Cost so far' : 'Cost'}>
          <Money value={Math.round(cost * 100) / 100} />
        </Stat>
        <Stat label={running ? 'Time left' : 'Duration'}>
          {running ? (secondsLeft === null ? '–' : formatDuration(secondsLeft)) : `${Math.round(session.duration_minutes)} min`}
        </Stat>
      </dl>

      {running ? (
        <>
          {session.can_stop && (
            <Button size="lg" variant="danger" fullWidth icon={<Square className="size-4 fill-current" aria-hidden="true" />} onClick={() => setConfirmingStop(true)}>
              Stop charging
            </Button>
          )}
          <p className="text-center text-xs text-muted">
            You pay for the energy you use, after charging. It stops by itself at {session.planned_stop_at ? formatTimeIST(session.planned_stop_at) : 'the end of your slot'}.
          </p>
        </>
      ) : (
        <SessionSummary session={session} />
      )}

      <Sheet
        open={confirmingStop}
        onClose={() => setConfirmingStop(false)}
        title="Stop charging?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmingStop(false)} disabled={stopping}>
              Keep charging
            </Button>
            <Button variant="danger" loading={stopping} onClick={() => void stop()}>
              Stop now
            </Button>
          </>
        }
      >
        <p className="text-sm">
          You have charged <span className="num font-bold">{session.energy_kwh.toFixed(1)} kWh</span> so far, which is about{' '}
          <Money value={session.cost_so_far} className="font-bold" />. Stopping ends the session and your bill is worked out up to this moment.
        </p>
        {stopError && (
          <p role="alert" className="mt-3 text-sm font-medium text-danger-soft">
            {stopError}
          </p>
        )}
      </Sheet>
    </div>
  );
};
