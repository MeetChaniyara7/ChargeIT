import { useState } from 'react';
import type { FormEvent } from 'react';
import { Maximize, PlugZap } from 'lucide-react';
import { KioskButton } from '../components/KioskButton';
import { Logo } from '../components/Logo';
import { Spinner } from '../components/Spinner';
import { ApiError, kioskFetch, keyStorage } from '../lib/api';
import { useIdleTimer } from '../lib/useIdleTimer';
import type { KioskStatus } from '../lib/api';

interface SetupScreenProps {
  /** Called once the pasted key has been checked with the server and saved. */
  onConnected: () => void;
  /** Present when the kiosk already has a key (the setup screen was opened on purpose): lets staff go back. */
  onCancel?: () => void;
  /** Why we are here again, e.g. "This kiosk key is not valid any more." */
  notice?: string | null;
  /** The station this tablet is set up for right now (shown when staff open this screen on purpose). */
  currentStation?: string | null;
  /** After this many seconds without a touch a screen that was opened on purpose closes itself. */
  idleSeconds?: number;
}

function explain(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'INVALID_DEVICE_KEY') return 'That key is not valid. Check that you copied all of it, with nothing added at the end.';
    if (error.code === 'DEVICE_DISABLED') return 'This kiosk has been switched off. Ask the station owner for a new key.';
    if (error.isOffline) return 'Cannot reach the ChargeSpot server. Check the tablet’s internet connection and try again.';
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

/** First run: paste the kiosk key once. The server checks it before it is saved on this tablet. */
export function SetupScreen({ onConnected, onCancel, notice, currentStation, idleSeconds = 60 }: SetupScreenProps) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stationName, setStationName] = useState<string | null>(null);

  // Opened on purpose by someone who then walked away: go back to the board instead of staying on this screen.
  useIdleTimer(Boolean(onCancel) && !busy && stationName === null, idleSeconds, () => onCancel?.());

  const connect = async (event: FormEvent) => {
    event.preventDefault();
    const key = value.trim();
    if (!key) {
      setError('Paste the kiosk key first.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const status = await kioskFetch<KioskStatus>('/api/kiosk/status', { key });
      keyStorage.set(key);
      setStationName(status.station_name);
      window.setTimeout(onConnected, 1200); // long enough to read which station this is
    } catch (e) {
      setError(explain(e));
      setBusy(false);
    }
  };

  const fullscreen = () => {
    void document.documentElement.requestFullscreen?.().catch(() => undefined);
  };

  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-8 px-12">
      <Logo />
      <form onSubmit={connect} className="w-full max-w-3xl space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-5xl font-extrabold">{currentStation ? 'Change station' : 'Set up this kiosk'}</h1>
          <p className="text-xl text-muted">
            {currentStation
              ? `This tablet is set up for ${currentStation}. To move it to another station, paste that station's kiosk key below. Press Cancel to keep things as they are.`
              : 'Paste the kiosk key you were given for this station. You only do this once.'}
          </p>
        </div>
        {notice && (
          <p role="alert" className="rounded-card border-2 border-warning/60 bg-warning/10 p-4 text-center text-xl">
            {notice}
          </p>
        )}
        <label className="block space-y-2">
          <span className="text-xl font-bold">Kiosk key</span>
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={2}
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            placeholder="ks_xxxxxxxx_…"
            className="block w-full select-text resize-none rounded-card border-2 border-field-border bg-raised p-4 font-mono text-xl text-fg placeholder:text-muted"
          />
        </label>
        {error && (
          <p role="alert" className="text-center text-xl font-bold text-danger-soft">
            {error}
          </p>
        )}
        {stationName ? (
          <p role="status" className="flex items-center justify-center gap-3 text-2xl font-bold text-primary">
            <PlugZap className="size-8" aria-hidden="true" />
            Connected to {stationName}
          </p>
        ) : (
          <div className="flex flex-wrap justify-center gap-4">
            <KioskButton type="submit" disabled={busy} icon={busy ? <Spinner /> : undefined}>
              {busy ? 'Checking…' : 'Connect this kiosk'}
            </KioskButton>
            {onCancel && (
              <KioskButton variant="secondary" onClick={onCancel}>
                Cancel
              </KioskButton>
            )}
            <KioskButton variant="secondary" onClick={fullscreen} icon={<Maximize className="size-6" aria-hidden="true" />}>
              Full screen
            </KioskButton>
          </div>
        )}
      </form>
    </div>
  );
}
