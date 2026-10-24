import { useEffect } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { KioskButton } from '../components/KioskButton';
import type { WalkInStopOut } from '../lib/api';
import { rupees } from '../lib/format';
import { useCountdown } from '../lib/useCountdown';

export const STOPPED_SECONDS = 20;

interface StoppedScreenProps {
  result: WalkInStopOut;
  onDone: () => void;
}

/** After a walk-in stopped early: what was used and what comes back. The refund is recorded by the server, not decided here. */
export function StoppedScreen({ result, onDone }: StoppedScreenProps) {
  const left = useCountdown(STOPPED_SECONDS, 'stopped');
  useEffect(() => {
    if (left === 0) onDone();
  }, [left, onDone]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-12 text-center">
      <CheckCircle2 className="size-20 text-primary" aria-hidden="true" />
      <h1 className="text-5xl font-extrabold" role="status">
        Charging stopped on Charger {result.charger_label}
      </h1>
      <dl className="grid grid-cols-3 gap-8 text-2xl">
        <div>
          <dt className="text-muted">You paid</dt>
          <dd className="num text-4xl font-extrabold">{rupees(result.prepaid)}</dd>
        </div>
        <div>
          <dt className="text-muted">Energy used</dt>
          <dd className="num text-4xl font-extrabold">{rupees(result.used)}</dd>
        </div>
        <div>
          <dt className="text-muted">Coming back to you</dt>
          <dd className="num text-4xl font-extrabold text-primary">{rupees(result.refunded)}</dd>
        </div>
      </dl>
      <p className="max-w-2xl text-xl text-muted">The unused amount is returned to the account you paid from. Please unplug your vehicle.</p>
      <KioskButton variant="secondary" onClick={onDone}>
        Done · back to the board ({left ?? STOPPED_SECONDS})
      </KioskButton>
    </div>
  );
}
