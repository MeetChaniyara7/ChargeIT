import { useEffect } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { ConnectorIcon } from '../components/ConnectorIcon';
import { KioskButton } from '../components/KioskButton';
import { useCountdown } from '../lib/useCountdown';

export const STARTED_SECONDS = 8;
export const STOP_CODE_SECONDS = 25;

interface StartedScreenProps {
  chargerLabel: string;
  connectorType: string;
  /** "Payment received" for a walk-in, "Code accepted" for a booking. */
  headline: string;
  /** A walk-in's stop code. Shown once, so the screen stays longer and asks the person to note it. */
  stopCode?: string | null;
  onDone: () => void;
}

/** Full screen: which charger to walk to. Goes back to the board by itself after 8 seconds. */
export function StartedScreen({ chargerLabel, connectorType, headline, stopCode, onDone }: StartedScreenProps) {
  const left = useCountdown(stopCode ? STOP_CODE_SECONDS : STARTED_SECONDS, 'started');
  useEffect(() => {
    if (left === 0) onDone();
  }, [left, onDone]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-12 text-center">
      <CheckCircle2 className="size-20 text-primary" aria-hidden="true" />
      <p className="text-3xl font-bold text-primary">{headline}</p>
      <h1 className="text-6xl font-extrabold leading-tight" role="status">
        Go to Charger {chargerLabel}
        <br />
        and plug in
      </h1>
      <p className="text-3xl">
        <ConnectorIcon type={connectorType} className="gap-3 [&_svg]:size-9" />
      </p>
      {stopCode && (
        <div className="rounded-card border-2 border-warning bg-surface px-8 py-4">
          <p className="text-xl font-bold">Your stop code. Note it down: it is shown only now.</p>
          <p className="num text-6xl font-extrabold tracking-[0.3em]" aria-label={`Stop code ${stopCode.split('').join(' ')}`}>
            {stopCode}
          </p>
          <p className="text-lg text-muted">To stop early and get the unused money back, press “Stop &amp; refund” on the board.</p>
        </div>
      )}
      <KioskButton variant="secondary" onClick={onDone}>
        Done · back to the board ({left ?? (stopCode ? STOP_CODE_SECONDS : STARTED_SECONDS)})
      </KioskButton>
    </div>
  );
}
