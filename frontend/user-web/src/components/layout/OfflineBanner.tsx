import { WifiOff } from 'lucide-react';
import { useOnline } from '../../lib/useOnline';

/** A slim bar across the top while the device is offline. Page content stays visible underneath, and it goes away by itself. */
export function OfflineBanner() {
  const online = useOnline();
  if (online) return null;
  return (
    <div role="status" className="fixed inset-x-4 bottom-20 z-50 mx-auto flex max-w-md items-center justify-center gap-2 rounded-card bg-danger-strong px-4 py-2 text-sm font-bold text-white shadow-e2 md:bottom-4 print:hidden">
      <WifiOff className="size-4" aria-hidden="true" />
      You are offline. We will reconnect when your connection is back.
    </div>
  );
}
