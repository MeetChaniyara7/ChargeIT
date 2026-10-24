import type { ReactNode } from 'react';
import { Button } from './Button';
import { Sheet } from './Sheet';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  /** A red confirm button, for things that cancel bookings or switch something off. */
  danger?: boolean;
  /** Shows a spinner on the confirm button and blocks both buttons. */
  busy?: boolean;
  /** An error from the last attempt, shown above the buttons. */
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
}

/** "Are you sure?": a sheet on phones, a dialog on desktop, with Cancel and a confirm button. */
export function ConfirmDialog({ open, title, children, confirmLabel, cancelLabel = 'Cancel', danger, busy, error, onConfirm, onClose }: ConfirmDialogProps) {
  return (
    <Sheet
      open={open}
      onClose={busy ? () => undefined : onClose}
      title={title}
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={busy}>
            {confirmLabel}
          </Button>
        </div>
      }
    >
      <div className="space-y-3 text-sm">
        {children}
        {error && (
          <p role="alert" className="font-medium text-danger-soft">
            {error}
          </p>
        )}
      </div>
    </Sheet>
  );
}
