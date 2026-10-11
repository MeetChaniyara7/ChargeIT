import { useCallback, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { CheckCircle2, Info, XCircle } from 'lucide-react';
import { cx } from './cx';
import { ToastContext } from './toast-context';
import type { ToastApi, ToastTone } from './toast-context';

interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

const ICONS: Record<ToastTone, ReactNode> = {
  success: <CheckCircle2 className="size-5 shrink-0 text-primary" aria-hidden="true" />,
  error: <XCircle className="size-5 shrink-0 text-danger" aria-hidden="true" />,
  info: <Info className="size-5 shrink-0 text-info" aria-hidden="true" />,
};

const DURATION_MS: Record<ToastTone, number> = { success: 4000, info: 4000, error: 7000 };

/**
 * Provides useToast() to the whole app and renders the messages. Messages disappear on
 * their own and are announced politely to screen readers. On phones they sit above the
 * bottom tab bar; on desktop they sit in the bottom-right corner.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const show = useCallback((tone: ToastTone, message: string) => {
    const id = nextId.current++;
    setToasts((current) => [...current.slice(-2), { id, tone, message }]); // keep at most 3
    window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), DURATION_MS[tone]);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => show('success', message),
      error: (message) => show('error', message),
      info: (message) => show('info', message),
    }),
    [show],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-4 bottom-20 z-[60] flex flex-col items-stretch gap-2 md:inset-x-auto md:bottom-4 md:right-4 md:w-96"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cx(
              'pointer-events-auto flex items-start gap-3 rounded-card border border-border bg-raised p-3 text-sm shadow-e3',
            )}
          >
            {ICONS[toast.tone]}
            <p className="flex-1">{toast.message}</p>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
