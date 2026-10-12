import React from 'react';
import { cx } from '../../components/ui';
import { formatCountdown } from './format';

interface HoldRingProps {
  secondsLeft: number;
  /** 1 = the whole hold is left, 0 = none. */
  fraction: number;
}

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** The countdown ring on the Hold & pay screen. It turns amber in the last minute. */
export const HoldRing: React.FC<HoldRingProps> = ({ secondsLeft, fraction }) => {
  const urgent = secondsLeft < 60;
  // Screen readers hear a short message every 15 seconds, not every tick.
  const announced = secondsLeft <= 0 ? 'The hold has run out.' : `About ${Math.ceil(secondsLeft / 15) * 15} seconds left to pay.`;
  return (
    <div className="relative mx-auto size-40" role="timer" aria-label="Time left to pay">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden="true">
        <circle cx="60" cy="60" r={RADIUS} fill="none" strokeWidth="8" className="stroke-border" />
        <circle
          cx="60" cy="60" r={RADIUS} fill="none" strokeWidth="8" strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE} strokeDashoffset={CIRCUMFERENCE * (1 - fraction)}
          className={cx('transition-[stroke-dashoffset] duration-300 ease-linear', urgent ? 'stroke-warning' : 'stroke-primary')}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cx('num text-display font-bold', urgent && 'text-warning')}>{formatCountdown(secondsLeft)}</span>
        <span className="text-xs text-muted">left to pay</span>
      </div>
      <p className="sr-only" aria-live="polite">
        {urgent ? announced : ''}
      </p>
    </div>
  );
};
