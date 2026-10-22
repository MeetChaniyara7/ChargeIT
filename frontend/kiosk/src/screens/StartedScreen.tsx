import { useEffect } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { ConnectorIcon } from '../components/ConnectorIcon';
import { KioskButton } from '../components/KioskButton';
import { useCountdown } from '../lib/useCountdown';

export const STARTED_SECONDS = 8;

interface StartedScreenProps {
  chargerLabel: string;
  connectorType: string;
  /** "Payment received" for a walk-in, "Code accepted" for a booking. */
  headline: string;
  onDone: () => void;
}

/** Full screen: which charger to walk to. Goes back to the board by itself after 8 seconds. */
export function StartedScreen({ chargerLabel, connectorType, headline, onDone }: StartedScreenProps) {
  const left = useCountdown(STARTED_SECONDS, 'started');
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
      <KioskButton variant="secondary" onClick={onDone}>
        Done · back to the board ({left ?? STARTED_SECONDS})
      </KioskButton>
    </div>
  );
}
