import { useId } from 'react';
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';
import { cx } from './cx';

/** The accessibility attributes Field hands to its input so label, hint and error are linked. */
export interface FieldControlProps {
  id: string;
  'aria-describedby'?: string;
  'aria-invalid'?: true;
}

export interface FieldProps {
  label: string;
  hint?: string;
  /** When set, the field is shown as invalid and the message is read out by screen readers. */
  error?: string | null;
  className?: string;
  /** Render the input, spreading the given props onto it: {(p) => <TextInput {...p} />} */
  children: (control: FieldControlProps) => ReactNode;
}

/** A label, an input, and optional hint and error text, wired together for screen readers. */
export function Field({ label, hint, error, className, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ');

  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children({
        id,
        'aria-describedby': describedBy || undefined,
        'aria-invalid': error ? true : undefined,
      })}
      {hint && !error && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

const CONTROL =
  'min-h-11 w-full rounded-control border border-field-border bg-surface px-3 text-base text-fg ' +
  'placeholder:text-muted transition-colors duration-150 hover:bg-raised ' +
  'aria-[invalid=true]:border-danger disabled:opacity-50';

/** A single-line text input (text, email, password, search, ...). */
export function TextInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(CONTROL, className)} {...rest} />;
}

/** A drop-down list. */
export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(CONTROL, 'pr-8', className)} {...rest}>
      {children}
    </select>
  );
}
