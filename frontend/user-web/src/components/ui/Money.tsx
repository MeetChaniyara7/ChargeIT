import { formatINR } from '@chargespot/shared';
import { cx } from './cx';

export interface MoneyProps {
  /** Amount in rupees. Missing values show a dash, never an invented number. */
  value: number | null | undefined;
  /** Adds "/kWh" for energy prices. */
  perKwh?: boolean;
  className?: string;
}

/** Rupees with Indian digit grouping and fixed-width numbers, e.g. "₹1,23,456.50". */
export function Money({ value, perKwh = false, className }: MoneyProps) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return <span className={cx('num text-muted', className)} aria-label="Unknown">—</span>;
  }
  return (
    <span className={cx('num', className)}>
      {formatINR(value)}
      {perKwh && <span className="text-muted">/kWh</span>}
    </span>
  );
}
