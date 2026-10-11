import { formatDateIST, formatRelativeIST, formatTimeIST } from '@chargespot/shared';
import { cx } from './cx';

export interface DateTimeProps {
  /** A UTC timestamp (ISO string or Date). Always shown in India time. */
  value: string | Date | null | undefined;
  /**
   * datetime = "Today, 4:30 PM" / "Tomorrow, 9:00 AM" / "Sun 13 Oct, 4:30 PM"
   * date     = "Today" / "Tomorrow" / "Sun 13 Oct"
   * time     = "4:30 PM"
   */
  format?: 'datetime' | 'date' | 'time';
  className?: string;
}

/** A date and/or time for people, in IST, with a machine-readable <time> element. */
export function DateTime({ value, format = 'datetime', className }: DateTimeProps) {
  if (!value) return <span className={cx('text-muted', className)}>—</span>;
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return <span className={cx('text-muted', className)}>—</span>;

  const text =
    format === 'time'
      ? formatTimeIST(date)
      : format === 'date'
        ? formatRelativeIST(date, { withTime: false })
        : formatRelativeIST(date);

  return (
    <time dateTime={date.toISOString()} className={cx('num', className)} title={`${formatDateIST(date)}, ${formatTimeIST(date)} IST`}>
      {text}
    </time>
  );
}
