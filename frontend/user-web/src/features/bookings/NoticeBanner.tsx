import React from 'react';
import { AlertTriangle, ArrowRightLeft, Ban } from 'lucide-react';
import { cx } from '../../components/ui';

const KINDS: Record<string, { icon: React.ElementType; box: string; label: string }> = {
  MOVED: { icon: ArrowRightLeft, box: 'border-info/50 bg-info/10', label: 'Your booking moved' },
  WARNING: { icon: AlertTriangle, box: 'border-warning/50 bg-warning/10', label: 'Heads up' },
  CANCELLED_NO_CHARGER: { icon: Ban, box: 'border-danger/50 bg-danger/10', label: 'Your booking was cancelled' },
};

/**
 * A highlighted line on a booking when its charger's situation changed it: moved to another charger,
 * a warning that the charger may be busy, or cancelled because none was free (fee refunded).
 */
export const NoticeBanner: React.FC<{ kind: string | null | undefined; text: string | null | undefined; className?: string }> = ({ kind, text, className }) => {
  if (!kind || !text) return null;
  const style = KINDS[kind] ?? KINDS.WARNING;
  const Icon = style.icon;
  return (
    <div role={kind === 'CANCELLED_NO_CHARGER' ? 'alert' : 'status'} className={cx('flex items-start gap-2.5 rounded-control border p-2.5 text-sm', style.box, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>
        <span className="font-bold">{style.label}: </span>
        {text}
      </p>
    </div>
  );
};
