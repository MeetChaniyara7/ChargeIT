import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx } from './cx';

type Variant = 'primary' | 'secondary' | 'danger';

// No hover styles anywhere: a touch screen has no pointer to hover with. `active:` shows the press.
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-on-primary active:bg-primary-strong',
  secondary: 'bg-raised text-fg border-2 border-field-border active:bg-border',
  danger: 'bg-danger-strong text-white active:bg-danger-strong/80',
};

export interface KioskButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  icon?: ReactNode;
  /** Fill the width of the parent. */
  block?: boolean;
}

/** The only button on the kiosk: at least 80 px tall (4rem at the kiosk root size of 20 px), 25 px bold text. */
export function KioskButton({ variant = 'primary', icon, block = false, className, children, type = 'button', ...rest }: KioskButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        'inline-flex min-h-16 items-center justify-center gap-3 rounded-card px-8 text-xl font-bold',
        'transition-colors duration-150 disabled:opacity-40',
        VARIANTS[variant],
        block && 'w-full',
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
