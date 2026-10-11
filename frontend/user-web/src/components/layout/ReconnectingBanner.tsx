import { Spinner } from '../ui';

/**
 * A slim bar for the top of the page, shown while the connection to the server is lost
 * (used from Phase 5 for live updates). Page content stays visible underneath.
 */
export function ReconnectingBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <div role="status" className="flex items-center justify-center gap-2 bg-warning px-4 py-1.5 text-sm font-bold text-black">
      <Spinner className="size-3.5" />
      Reconnecting…
    </div>
  );
}
