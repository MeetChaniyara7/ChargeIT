import type { HTMLAttributes, ReactNode } from 'react';
import type { Availability } from './availability';
import { cx } from './cx';

export type BadgeTone = 'neutral' | 'primary' | 'info' | 'warning' | 'danger';

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-raised text-muted border-border',
  primary: 'bg-primary/15 text-primary border-primary/30',
  info: 'bg-info/15 text-info border-info/30',
  warning: 'bg-warning/15 text-warning border-warning/30',
  danger: 'bg-danger/15 text-danger-soft border-danger/30',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  icon?: ReactNode;
}

/** A small label, e.g. "Admin" or "No-show". */
export function Badge({ tone = 'neutral', icon, className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-bold',
        TONES[tone],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </span>
  );
}

const STATUS: Record<Availability, { label: string; tone: BadgeTone; dot: string }> = {
  free: { label: 'Free', tone: 'primary', dot: 'bg-primary' },
  few: { label: 'Few left', tone: 'warning', dot: 'bg-warning' },
  busy: { label: 'Busy', tone: 'danger', dot: 'bg-danger' },
  offline: { label: 'Offline', tone: 'neutral', dot: 'bg-muted' },
};

/** Charger or station availability. Always shows a word as well as a colour. */
export function StatusBadge({ status, label, className }: { status: Availability; label?: string; className?: string }) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone} className={className}>
      <span className={cx('size-2 rounded-full', s.dot)} aria-hidden="true" />
      {label ?? s.label}
    </Badge>
  );
}
