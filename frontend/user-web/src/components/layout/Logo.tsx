import { Link } from 'react-router-dom';
import { cx } from '../ui';

/** The ChargeSpot mark: a lightning bolt in a green rounded square, with the wordmark. */
export function Logo({ to = '/', className }: { to?: string; className?: string }) {
  return (
    <Link to={to} className={cx('inline-flex items-center gap-2.5 rounded-control', className)} aria-label="ChargeSpot home">
      <span className="flex size-9 items-center justify-center rounded-control bg-primary text-on-primary">
        <svg viewBox="0 0 24 24" className="size-5" fill="currentColor" aria-hidden="true">
          <path d="M13.2 2 5 13.5h5.3L9.4 22 19 9.8h-5.6z" />
        </svg>
      </span>
      <span className="text-xl font-bold tracking-tight">ChargeSpot</span>
    </Link>
  );
}
