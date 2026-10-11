import { cx } from './cx';

type SkeletonProps = { className?: string };

// Grey placeholder shapes shown while data loads. They are hidden from screen readers;
// a page announces loading with its own status text where that matters.
const BASE = 'animate-pulse bg-raised';

/** A line of text. Set the width with className, e.g. "w-40". */
export function SkeletonLine({ className }: SkeletonProps) {
  return <div aria-hidden="true" className={cx(BASE, 'h-4 w-full rounded', className)} />;
}

/** A rectangle, e.g. a card or an image. */
export function SkeletonBlock({ className }: SkeletonProps) {
  return <div aria-hidden="true" className={cx(BASE, 'h-24 w-full rounded-card', className)} />;
}

/** A circle, e.g. an avatar. */
export function SkeletonCircle({ className }: SkeletonProps) {
  return <div aria-hidden="true" className={cx(BASE, 'size-10 rounded-full', className)} />;
}
