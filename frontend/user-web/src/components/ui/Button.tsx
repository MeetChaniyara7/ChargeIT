import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { buttonClasses, VARIANTS } from './button-styles';
import type { ButtonSize, ButtonVariant } from './button-styles';
import { cx } from './cx';
import { Spinner } from './Spinner';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and blocks clicks. The label stays so the button keeps its width. */
  loading?: boolean;
  /** An icon shown before the label. */
  icon?: ReactNode;
  fullWidth?: boolean;
}

/** The one button used everywhere. */
export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  fullWidth = false,
  className,
  disabled,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(buttonClasses({ variant, size, fullWidth }), className)}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  /** Required: icon-only buttons have no visible text, so screen readers need this. */
  'aria-label': string;
  variant?: ButtonVariant;
  children: ReactNode;
}

/** A square icon-only button (44 x 44 px). */
export function IconButton({ variant = 'ghost', className, children, type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        'inline-flex size-11 items-center justify-center rounded-control transition-colors duration-150',
        'disabled:opacity-50',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
