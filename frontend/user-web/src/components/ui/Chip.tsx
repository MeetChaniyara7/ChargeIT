import type { ButtonHTMLAttributes } from 'react';
import { cx } from './cx';

export interface ChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> {
  selected: boolean;
  onSelectedChange: (selected: boolean) => void;
}

/** A toggle button for filters, e.g. "CCS2" or "Fast 50 kW+". */
export function Chip({ selected, onSelectedChange, className, children, type = 'button', ...rest }: ChipProps) {
  return (
    <button
      type={type}
      aria-pressed={selected}
      onClick={() => onSelectedChange(!selected)}
      className={cx(
        'inline-flex min-h-11 items-center gap-1.5 rounded-full border px-3 text-sm font-medium transition-colors duration-150',
        selected
          ? 'border-primary bg-primary/15 text-primary'
          : 'border-field-border bg-surface text-fg hover:bg-raised',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
