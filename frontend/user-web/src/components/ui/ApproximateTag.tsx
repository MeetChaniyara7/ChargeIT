import { useId } from 'react';
import { cx } from './cx';

export interface ApproximateTagProps {
  /** Why the value is approximate, e.g. "Price estimated from typical Tata Power tariffs". */
  reason?: string;
  className?: string;
}

/**
 * A dotted-outline "Approximate" tag shown wherever a value was generated or estimated
 * instead of imported. It is a focusable button so keyboard and screen-reader users get
 * the explanation too; the tooltip shows on hover and on focus.
 */
export function ApproximateTag({
  reason = 'Some details are estimated from typical values for this operator.',
  className,
}: ApproximateTagProps) {
  const tipId = useId();
  return (
    <span className={cx('group relative inline-flex', className)}>
      <button
        type="button"
        aria-describedby={tipId}
        className="inline-flex items-center rounded-full border border-dotted border-muted px-2 py-0.5 text-xs font-medium text-muted"
      >
        Approximate
      </button>
      <span
        id={tipId}
        role="tooltip"
        className={cx(
          'pointer-events-none absolute left-0 top-full z-30 mt-1 hidden w-56 rounded-control border border-border',
          'bg-raised p-2 text-xs text-fg shadow-e2 group-focus-within:block group-hover:block',
        )}
      >
        {reason}
      </span>
    </span>
  );
}
