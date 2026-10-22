import type { HTMLAttributes } from 'react';

/**
 * The ChargeSpot mark. Pressing and holding it for 3 seconds opens the setup screen again: staff know about it,
 * nobody else looks for it (pass the props from useLongPress).
 */
export function Logo(props: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className="inline-flex items-center gap-3" {...props}>
      <span className="flex size-12 items-center justify-center rounded-control bg-primary text-on-primary" aria-hidden="true">
        <svg viewBox="0 0 24 24" className="size-7" fill="currentColor">
          <path d="M13.2 2 5 13.5h5.3L9.4 22 19 9.8h-5.6z" />
        </svg>
      </span>
      <span className="text-2xl font-extrabold tracking-tight">ChargeSpot</span>
    </div>
  );
}
