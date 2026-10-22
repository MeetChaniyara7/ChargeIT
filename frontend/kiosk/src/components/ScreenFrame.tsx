import type { ReactNode } from 'react';
import { formatTimeIST } from '@chargespot/shared';
import { useLongPress } from '../lib/useLongPress';
import { Logo } from './Logo';

interface ScreenFrameProps {
  stationName: string | null;
  now: Date;
  /** Long-pressing the logo calls this (back to setup). */
  onSecret: () => void;
  children: ReactNode;
}

/** The header every screen shares: logo, station name and the clock (India time, taken from the server clock). */
export function ScreenFrame({ stationName, now, onSecret, children }: ScreenFrameProps) {
  const longPress = useLongPress(onSecret);
  return (
    <div className="flex h-dvh flex-col">
      <header className="flex h-20 shrink-0 items-center justify-between border-b border-border bg-surface px-8">
        <Logo {...longPress} />
        <p className="truncate px-6 text-xl font-bold text-muted">{stationName}</p>
        <p className="num text-3xl font-extrabold" aria-label="Time now">
          {formatTimeIST(now)}
        </p>
      </header>
      <main className="screen-in min-h-0 flex-1">{children}</main>
    </div>
  );
}
