import type { ReactNode } from 'react';
import { Settings } from 'lucide-react';
import { formatTimeIST } from '@chargespot/shared';
import { useLongPress } from '../lib/useLongPress';
import { Logo } from './Logo';

interface ScreenFrameProps {
  stationName: string | null;
  now: Date;
  /** Opens the setup screen (change the station, paste a new key). Also reachable by pressing and holding the logo. */
  onSecret: () => void;
  children: ReactNode;
}

/** The header every screen shares: logo, station name, a way to change the station, and the clock (India time, from the server clock). */
export function ScreenFrame({ stationName, now, onSecret, children }: ScreenFrameProps) {
  const longPress = useLongPress(onSecret);
  return (
    <div className="flex h-dvh flex-col">
      <header className="flex h-20 shrink-0 items-center justify-between gap-4 border-b border-border bg-surface px-8">
        <Logo {...longPress} />
        <p className="min-w-0 flex-1 truncate px-2 text-center text-xl font-bold text-muted">{stationName}</p>
        {/* Safe to tap: the setup screen keeps the current station until a valid new key is pasted, and it has a Cancel button. */}
        <button
          type="button"
          onClick={onSecret}
          className="inline-flex min-h-16 shrink-0 items-center gap-2 rounded-card border-2 border-border px-4 text-lg font-bold text-muted active:bg-raised"
        >
          <Settings className="size-6" aria-hidden="true" />
          <span className="hidden min-[1200px]:inline">Change station</span>
          <span className="sr-only min-[1200px]:hidden">Change station or enter a new kiosk key</span>
        </button>
        <p className="num shrink-0 text-3xl font-extrabold" aria-label="Time now">
          {formatTimeIST(now)}
        </p>
      </header>
      <main className="screen-in min-h-0 flex-1">{children}</main>
    </div>
  );
}
