import React from 'react';
import { Check } from 'lucide-react';
import { Badge, cx } from '../../components/ui';

const STEPS = [
  { id: 'HELD', label: 'Held' },
  { id: 'CONFIRMED', label: 'Confirmed' },
  { id: 'ACTIVE', label: 'Charging' },
  { id: 'COMPLETED', label: 'Done' },
] as const;

const ENDINGS: Record<string, { label: string; tone: 'danger' | 'neutral' | 'warning' }> = {
  CANCELLED: { label: 'Cancelled', tone: 'neutral' },
  EXPIRED: { label: 'Expired', tone: 'neutral' },
  NO_SHOW: { label: 'No-show · fee kept', tone: 'warning' },
};

/** Where a booking is: Held → Confirmed → Charging → Done, or how it ended (Cancelled, Expired, No-show). */
export const StatusTimeline: React.FC<{ status: string; className?: string }> = ({ status, className }) => {
  const ending = ENDINGS[status];
  if (ending) {
    return (
      <div className={className}>
        <Badge tone={ending.tone}>{ending.label}</Badge>
      </div>
    );
  }
  const current = Math.max(0, STEPS.findIndex((s) => s.id === status));
  return (
    <ol className={cx('flex items-center gap-1 text-xs', className)} aria-label="Booking progress">
      {STEPS.map((step, index) => {
        const done = index < current || status === 'COMPLETED';
        const active = index === current && status !== 'COMPLETED';
        return (
          <li key={step.id} className="flex items-center gap-1" aria-current={active ? 'step' : undefined}>
            <span
              className={cx(
                'flex size-5 items-center justify-center rounded-full border text-[10px] font-bold',
                done && 'border-primary bg-primary text-on-primary',
                active && 'border-primary text-primary',
                !done && !active && 'border-field-border text-muted',
              )}
            >
              {done ? <Check className="size-3" aria-hidden="true" /> : index + 1}
            </span>
            <span className={cx(active ? 'font-bold text-fg' : done ? 'text-fg' : 'text-muted')}>{step.label}</span>
            {index < STEPS.length - 1 && <span className="mx-1 h-px w-3 bg-border" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
};
