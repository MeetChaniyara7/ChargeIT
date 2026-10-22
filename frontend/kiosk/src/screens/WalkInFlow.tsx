import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, CheckCircle2, Clock, RotateCcw, Smartphone, TimerOff } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { formatTimeIST } from '@chargespot/shared';
import { ConnectorIcon } from '../components/ConnectorIcon';
import { cx } from '../components/cx';
import { KioskButton } from '../components/KioskButton';
import { Spinner } from '../components/Spinner';
import { ApiError, kioskFetch } from '../lib/api';
import type { ChargerTile, KioskStatus, WalkInOption, WalkInOut } from '../lib/api';
import { clockMinutes, kwhText, rupees } from '../lib/format';
import { blockedText } from '../lib/tiles';
import { useCountdown } from '../lib/useCountdown';
import { useIdleTimer } from '../lib/useIdleTimer';

/** How often the QR screen asks whether the payment has arrived. */
export const WALK_IN_POLL_MS = 2_000;

type Step =
  | { name: 'pick' }
  | { name: 'amount'; tile: ChargerTile }
  | { name: 'qr'; tile: ChargerTile; walkIn: WalkInOut; receivedAt: number }
  | { name: 'ended'; walkIn: WalkInOut };

interface WalkInFlowProps {
  status: KioskStatus;
  idleSeconds: number;
  refreshBoard: () => void;
  onExit: () => void;
  /** The payment arrived and charging has started. */
  onPaid: (chargerLabel: string, connectorType: string) => void;
}

function optionLabel(option: WalkInOption): string {
  return option.kind === 'UNTIL_NEXT' && option.until ? `Until ${formatTimeIST(option.until)}` : rupees(option.amount);
}

/** Take a charger without a booking: pick one, pick an amount, scan the QR with any UPI app, plug in. */
export function WalkInFlow({ status, idleSeconds, refreshBoard, onExit, onPaid }: WalkInFlowProps) {
  const [step, setStep] = useState<Step>({ name: 'pick' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The QR screen ends by itself (3 minutes, or paid). Every other screen goes back to the board after the idle time.
  useIdleTimer(step.name !== 'qr' && !busy, idleSeconds, onExit);

  const choose = async (tile: ChargerTile, option: WalkInOption) => {
    setBusy(true);
    setError(null);
    try {
      const walkIn = await kioskFetch<WalkInOut>('/api/kiosk/walk-ins', {
        method: 'POST',
        body: option.kind === 'UNTIL_NEXT' ? { charger_id: tile.charger_id, until_next: true } : { charger_id: tile.charger_id, amount: option.amount },
      });
      refreshBoard();
      setStep({ name: 'qr', tile, walkIn, receivedAt: performance.now() });
    } catch (e) {
      refreshBoard();
      if (e instanceof ApiError && !e.isOffline) {
        setError(e.code === 'CHARGER_BUSY' ? 'Sorry, someone just took that charger. Please choose another.' : e.message);
        setStep({ name: 'pick' });
      } else {
        setError('Cannot reach the server. Please try again in a moment.');
      }
    } finally {
      setBusy(false);
    }
  };

  if (step.name === 'pick') return <PickStep status={status} error={error} onBack={onExit} onPick={(tile) => { setError(null); setStep({ name: 'amount', tile }); }} />;
  if (step.name === 'amount') {
    return <AmountStep tile={step.tile} busy={busy} error={error} onBack={() => setStep({ name: 'pick' })} onChoose={(option) => void choose(step.tile, option)} />;
  }
  if (step.name === 'qr') {
    return (
      <QrStep
        tile={step.tile}
        initial={step.walkIn}
        onPaid={() => {
          refreshBoard();
          onPaid(step.tile.label, step.tile.connector_type);
        }}
        onEnded={(walkIn) => {
          refreshBoard();
          setStep({ name: 'ended', walkIn });
        }}
        onBack={() => {
          refreshBoard();
          onExit();
        }}
      />
    );
  }
  return <EndedStep walkIn={step.walkIn} onTryAgain={() => setStep({ name: 'pick' })} onExit={onExit} />;
}

// ---------------------------------------------------------------- step 1: which charger

function PickStep({ status, error, onBack, onPick }: { status: KioskStatus; error: string | null; onBack: () => void; onPick: (tile: ChargerTile) => void }) {
  const free = status.chargers.filter((c) => c.can_walk_in);
  return (
    <div className="flex h-full flex-col gap-5 p-8 min-[1200px]:gap-6">
      <div className="space-y-2">
        <h1 className="text-4xl font-extrabold min-[1200px]:text-5xl">Which charger?</h1>
        <p className="text-xl text-muted">Pick a free charger. You pay first with any UPI app, then plug in.</p>
      </div>
      {error && (
        <p role="alert" className="text-2xl font-bold text-danger-soft">
          {error}
        </p>
      )}
      {free.length === 0 ? (
        <div className="flex-1 space-y-4">
          <p className="text-3xl font-bold">No charger is free for walk-ins right now.</p>
          <ul className="space-y-1 text-xl text-muted">
            {status.chargers.map((c) => (
              <li key={c.charger_id}>
                {c.label}: {c.state === 'FREE' || c.state === 'RESERVED' ? blockedText(c.walk_in_blocked_reason) : c.state === 'CHARGING' ? 'Charging' : c.state === 'PAYING' ? 'Being taken' : 'Out of service'}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <ul className="grid min-h-0 flex-1 grid-cols-2 content-start gap-5 overflow-y-auto">
          {free.map((tile) => (
            <li key={tile.charger_id}>
              <button
                type="button"
                onClick={() => onPick(tile)}
                className="flex min-h-32 w-full items-center justify-between gap-4 rounded-card border-2 border-primary/60 bg-surface p-5 text-left active:bg-raised"
              >
                <span className="space-y-1">
                  <span className="block text-4xl font-extrabold">{tile.label}</span>
                  <span className="flex flex-wrap items-center gap-x-4 text-lg text-muted">
                    <ConnectorIcon type={tile.connector_type} className="text-fg" />
                    {tile.power_kw != null && <span>{tile.power_kw} kW</span>}
                    {tile.price_per_kwh != null && <span className="num">{rupees(tile.price_per_kwh)}/kWh</span>}
                  </span>
                </span>
                <span className="text-right text-xl font-bold text-primary">{tile.free_until ? `Free until ${formatTimeIST(tile.free_until)}` : 'Free'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div>
        <KioskButton variant="secondary" icon={<ArrowLeft className="size-7" aria-hidden="true" />} onClick={onBack}>
          Back
        </KioskButton>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- step 2: how much

function AmountStep({
  tile, busy, error, onBack, onChoose,
}: { tile: ChargerTile; busy: boolean; error: string | null; onBack: () => void; onChoose: (option: WalkInOption) => void }) {
  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-8 min-[1200px]:gap-6">
      <div className="space-y-2">
        <h1 className="text-4xl font-extrabold min-[1200px]:text-5xl">How much for Charger {tile.label}?</h1>
        <p className="text-xl text-muted">
          {tile.price_per_kwh != null ? `${rupees(tile.price_per_kwh)} per kWh. ` : ''}
          Charging stops when the money is used up. Whatever is left is refunded.
        </p>
      </div>
      {error && (
        <p role="alert" className="text-2xl font-bold text-danger-soft">
          {error}
        </p>
      )}
      <ul className="grid flex-1 grid-cols-2 content-start gap-5">
        {tile.options.map((option) => (
          <li key={option.kind + option.amount}>
            <button
              type="button"
              disabled={busy}
              onClick={() => onChoose(option)}
              className={cx(
                'flex min-h-28 w-full flex-col items-start justify-center gap-1 rounded-card border-2 bg-surface p-5 text-left active:bg-raised disabled:opacity-40 min-[1200px]:min-h-36 min-[1200px]:p-6',
                option.kind === 'UNTIL_NEXT' ? 'border-info/60' : 'border-primary/60',
              )}
            >
              <span className="text-4xl font-extrabold min-[1200px]:text-5xl">{optionLabel(option)}</span>
              <span className="text-xl text-muted">
                {option.kind === 'UNTIL_NEXT' ? `${rupees(option.amount)} · about ${kwhText(option.kwh)}` : `about ${kwhText(option.kwh)}`}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-6">
        <KioskButton variant="secondary" icon={<ArrowLeft className="size-7" aria-hidden="true" />} onClick={onBack} disabled={busy}>
          Back
        </KioskButton>
        {busy && (
          <p className="flex items-center gap-3 text-2xl text-muted">
            <Spinner />
            Getting your payment code…
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- step 3: the QR code

function QrStep({
  tile, initial, onPaid, onEnded, onBack,
}: { tile: ChargerTile; initial: WalkInOut; onPaid: () => void; onEnded: (walkIn: WalkInOut) => void; onBack: () => void }) {
  const [walkIn, setWalkIn] = useState(initial);
  const [cancelling, setCancelling] = useState(false);
  const answered = useRef(false); // paid/ended can only be reported once
  // The newest callbacks, read by the polling loop: the loop itself must not restart every time the screen redraws.
  const callbacks = useRef({ onPaid, onEnded });
  useEffect(() => {
    callbacks.current = { onPaid, onEnded };
  });

  // The 3:00 countdown follows the server's number, counted on this device's stopwatch.
  const left = useCountdown(walkIn.seconds_left, walkIn.server_time);

  useEffect(() => {
    let stopped = false;
    const ask = async () => {
      try {
        const next = await kioskFetch<WalkInOut>(`/api/kiosk/walk-ins/${initial.walk_in_id}`);
        if (stopped || answered.current) return;
        setWalkIn(next);
        if (next.status === 'PAID') {
          answered.current = true;
          callbacks.current.onPaid();
        } else if (next.status !== 'WAITING_FOR_PAYMENT') {
          answered.current = true;
          callbacks.current.onEnded(next);
        }
      } catch {
        /* a dropped request: the next poll tries again (the connection overlay covers longer outages) */
      }
    };
    const timer = window.setInterval(() => void ask(), WALK_IN_POLL_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [initial.walk_in_id]);

  const back = async () => {
    setCancelling(true);
    try {
      await kioskFetch<WalkInOut>(`/api/kiosk/walk-ins/${initial.walk_in_id}/cancel`, { method: 'POST' });
    } catch {
      /* if it cannot be cancelled now, the 3-minute hold frees the charger by itself */
    }
    onBack();
  };

  const urgent = (left ?? 0) <= 30;
  return (
    <div className="flex h-full items-center justify-center gap-14 px-10">
      <div className="rounded-sheet bg-white p-6" aria-hidden={walkIn.payment_url ? undefined : true}>
        {walkIn.payment_url ? (
          // A QR code needs black on white to scan reliably, whatever the theme.
          <QRCodeSVG value={walkIn.payment_url} size={340} level="M" bgColor="#ffffff" fgColor="#000000" title="Payment QR code" />
        ) : (
          <div className="size-[340px]" />
        )}
      </div>

      <section className="w-[28rem] space-y-6">
        <div className="space-y-2">
          <h1 className="text-5xl font-extrabold">Scan to pay</h1>
          <p className="flex items-center gap-3 text-2xl">
            <Smartphone className="size-8 shrink-0 text-info" aria-hidden="true" />
            Scan with any UPI app
          </p>
        </div>
        <dl className="space-y-1 text-2xl">
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Charger</dt>
            <dd className="font-bold">{tile.label}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Amount</dt>
            <dd className="num font-bold">{rupees(walkIn.amount)}</dd>
          </div>
        </dl>
        <p className={cx('flex items-center gap-3 text-4xl font-extrabold', urgent ? 'text-warning' : 'text-fg')} aria-live="off">
          <Clock className="size-9" aria-hidden="true" />
          <span className="num" aria-label={`${left ?? 0} seconds left`}>
            {clockMinutes(left ?? 0)}
          </span>
        </p>
        <p className="flex items-center gap-3 text-xl text-muted" role="status">
          <Spinner />
          Waiting for your payment…
        </p>
        <KioskButton variant="secondary" disabled={cancelling} onClick={() => void back()}>
          Cancel
        </KioskButton>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- the QR ran out, or was cancelled

function EndedStep({ walkIn, onTryAgain, onExit }: { walkIn: WalkInOut; onTryAgain: () => void; onExit: () => void }) {
  const refunded = walkIn.refunded > 0;
  return (
    <div className="flex h-full flex-col items-center justify-center gap-8 px-12 text-center">
      {refunded ? <CheckCircle2 className="size-24 text-info" aria-hidden="true" /> : <TimerOff className="size-24 text-warning" aria-hidden="true" />}
      <h1 className="text-5xl font-extrabold">{refunded ? 'Your payment came too late' : walkIn.status === 'CANCELLED' ? 'Cancelled' : 'The payment code ran out'}</h1>
      <p className="max-w-3xl text-2xl text-muted">
        {refunded
          ? `${rupees(walkIn.refunded)} will be refunded to you in full, so you have not been charged. You can start again.`
          : 'If the payment did not go through, you have not been charged. If money was taken, it is refunded automatically. You can start again.'}
      </p>
      <div className="flex gap-5">
        <KioskButton icon={<RotateCcw className="size-7" aria-hidden="true" />} onClick={onTryAgain}>
          Start again
        </KioskButton>
        <KioskButton variant="secondary" onClick={onExit}>
          Back to the board
        </KioskButton>
      </div>
    </div>
  );
}
