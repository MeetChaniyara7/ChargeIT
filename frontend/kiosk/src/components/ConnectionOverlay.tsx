import { WifiOff } from 'lucide-react';
import { Spinner } from './Spinner';

/** Covers the screen while the server cannot be reached. The kiosk keeps asking by itself; nobody has to touch it. */
export function ConnectionOverlay() {
  return (
    <div role="alert" className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-bg/95 px-12 text-center">
      <WifiOff className="size-20 text-warning" aria-hidden="true" />
      <h2 className="text-5xl font-extrabold">Connection lost</h2>
      <p className="max-w-xl text-2xl text-muted">We can&apos;t reach ChargeSpot right now. We&apos;ll keep trying, and this screen will go away by itself.</p>
      <p className="flex items-center gap-3 text-xl text-muted">
        <Spinner />
        Trying again…
      </p>
    </div>
  );
}
