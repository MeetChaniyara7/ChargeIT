import type { ReactNode } from 'react';
import { cx } from './cx';

export interface EmptyStateProps {
  /** A simple icon or illustration. */
  icon?: ReactNode;
  title: string;
  text?: string;
  /** At most one clear next step, usually a Button or a link. */
  action?: ReactNode;
  className?: string;
}

/** What to show when there is nothing to show yet: say why, and offer one next step. */
export function EmptyState({ icon, title, text, action, className }: EmptyStateProps) {
  return (
    <div className={cx('flex flex-col items-center gap-3 px-6 py-12 text-center', className)}>
      {icon && (
        <div className="flex size-14 items-center justify-center rounded-full bg-raised text-muted" aria-hidden="true">
          {icon}
        </div>
      )}
      <h2 className="text-xl font-bold">{title}</h2>
      {text && <p className="max-w-sm text-sm text-muted">{text}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
