import React from 'react';
import { cx } from '../../components/ui';

interface BatteryRingProps {
  /** 0 to 100 (it may be a fraction while it glides to a new value). */
  percent: number;
  /** Charging is running: the ring glows and breathes. When it ends the glow stays, but still. */
  running: boolean;
}

const RADIUS = 104;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * The battery ring: the one glowing element in the whole app. It shows the charge level as an arc
 * with the percentage in the middle. (Glow and breathing are switched off by "reduce motion".)
 */
export const BatteryRing: React.FC<BatteryRingProps> = ({ percent, running }) => {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div
      role="progressbar"
      aria-label="Battery level"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className="relative mx-auto aspect-square w-full max-w-72"
    >
      <svg viewBox="0 0 240 240" className={cx('size-full -rotate-90', running ? 'battery-ring-live' : 'battery-ring-still')} aria-hidden="true">
        <circle cx="120" cy="120" r={RADIUS} fill="none" strokeWidth="14" className="stroke-border" />
        <circle
          cx="120" cy="120" r={RADIUS} fill="none" strokeWidth="14" strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE} strokeDashoffset={CIRCUMFERENCE * (1 - clamped / 100)}
          className="stroke-primary"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="num text-hero font-bold leading-none md:text-[3.5rem]">
          {Math.round(clamped)}
          <span className="text-xl text-muted">%</span>
        </span>
        <span className="mt-1 text-sm text-muted">battery</span>
      </div>
    </div>
  );
};
