import type { HTMLAttributes } from 'react';
import { cx } from './cx';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** 1 = sits on the page, 2 = floats above other cards (popovers, selected items). */
  elevation?: 1 | 2;
}

/** A solid surface with a thin border and a soft shadow. No glass: glass is for the map only. */
export function Card({ elevation = 1, className, ...rest }: CardProps) {
  return (
    <div
      className={cx(
        'rounded-card border border-border bg-surface',
        elevation === 1 ? 'shadow-e1' : 'shadow-e2',
        className,
      )}
      {...rest}
    />
  );
}

/** A thin horizontal line between sections. */
export function Divider({ className }: { className?: string }) {
  return <hr className={cx('border-0 border-t border-border', className)} />;
}
