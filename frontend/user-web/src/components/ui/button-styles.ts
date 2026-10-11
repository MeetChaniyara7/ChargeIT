import { cx } from './cx';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

// md and lg keep a tap target of at least 44 px (min-h-11). `sm` is for dense desktop
// toolbars and tables, not for the main actions on phone screens.
const SIZES: Record<ButtonSize, string> = {
  sm: 'min-h-9 px-3 text-sm',
  md: 'min-h-11 px-4 text-sm',
  lg: 'min-h-12 px-6 text-base',
};

export const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-on-primary hover:bg-primary-strong',
  secondary: 'bg-raised text-fg border border-field-border hover:bg-border',
  ghost: 'bg-transparent text-fg hover:bg-raised',
  danger: 'bg-danger-strong text-white hover:bg-danger-strong/85',
};

/**
 * The classes that make something look like a Button. Use it on a router <Link> that
 * should look like a button: <Link className={buttonClasses({ size: 'lg' })} to="/login">
 */
export function buttonClasses({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
}: { variant?: ButtonVariant; size?: ButtonSize; fullWidth?: boolean } = {}): string {
  return cx(
    'inline-flex items-center justify-center gap-2 rounded-control font-bold transition-colors duration-150',
    'disabled:opacity-50',
    SIZES[size],
    VARIANTS[variant],
    fullWidth && 'w-full',
  );
}
