import { useEffect, useState } from 'react';
import { KeyRound, Plug } from 'lucide-react';
import { ChargerTileCard } from '../components/ChargerTileCard';
import { cx } from '../components/cx';
import { KioskButton } from '../components/KioskButton';
import type { KioskStatus } from '../lib/api';
import { useIdleTimer } from '../lib/useIdleTimer';

/** After this long without a touch the board starts its gentle "attract" loop. */
export const ATTRACT_AFTER_SECONDS = 120;
const ATTRACT_STEP_MS = 3500;

const PROMPTS = ['Booked in the app? Enter your code', 'No booking? Pay by UPI and charge here'] as const;

interface BoardScreenProps {
  status: KioskStatus;
  onOtp: () => void;
  onWalkIn: () => void;
}

/** The home screen: every charger of this station, and the two ways to start. No personal data appears here. */
export function BoardScreen({ status, onOtp, onWalkIn }: BoardScreenProps) {
  const [attract, setAttract] = useState(false);
  const [step, setStep] = useState(0);

  useIdleTimer(!attract, ATTRACT_AFTER_SECONDS, () => setAttract(true));

  // While attracting: the two actions take turns glowing, with a matching line of text. Any touch ends it.
  useEffect(() => {
    if (!attract) return;
    const stop = () => setAttract(false);
    const timer = window.setInterval(() => setStep((n) => n + 1), ATTRACT_STEP_MS);
    window.addEventListener('pointerdown', stop, { once: true });
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('pointerdown', stop);
    };
  }, [attract]);

  const glow = attract ? step % 2 : -1;

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        {status.chargers.length === 0 ? (
          <p className="mt-24 text-center text-3xl font-bold text-muted">No chargers are set up at this station yet.</p>
        ) : (
          <ul className="grid grid-cols-2 gap-5">
            {status.chargers.map((tile) => (
              <li key={tile.charger_id} className="flex">
                <div className="flex-1">
                  <ChargerTileCard tile={tile} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <footer className="shrink-0 border-t border-border bg-surface p-5">
        {attract && (
          <p aria-live="polite" className="mb-3 text-center text-2xl font-bold text-primary">
            {PROMPTS[glow]}
          </p>
        )}
        <div className="grid grid-cols-2 gap-5">
          <KioskButton
            variant="secondary"
            block
            icon={<KeyRound className="size-8" aria-hidden="true" />}
            onClick={onOtp}
            className={cx('min-h-24 text-2xl', glow === 0 && 'attract-glow')}
          >
            Booked? Enter your code
          </KioskButton>
          <KioskButton block icon={<Plug className="size-8" aria-hidden="true" />} onClick={onWalkIn} className={cx('min-h-24 text-2xl', glow === 1 && 'attract-glow')}>
            No booking? Charge here
          </KioskButton>
        </div>
      </footer>
    </div>
  );
}
