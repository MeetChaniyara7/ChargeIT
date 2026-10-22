import { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { cx } from '../components/cx';
import { Keypad } from '../components/Keypad';
import { KioskButton } from '../components/KioskButton';
import { ApiError, kioskFetch } from '../lib/api';
import type { OtpStartOut } from '../lib/api';
import { clockMinutes } from '../lib/format';
import { CODE_LENGTH, isComplete, otpFailureMessage, pressKey } from '../lib/otp';
import type { PadKey } from '../lib/otp';
import { useCountdown } from '../lib/useCountdown';
import { useIdleTimer } from '../lib/useIdleTimer';

interface OtpScreenProps {
  idleSeconds: number;
  onBack: () => void;
  onStarted: (result: OtpStartOut) => void;
}

/** Six big boxes and a number pad. The server checks the code; this screen only shows what it says. */
export function OtpScreen({ idleSeconds, onBack, onStarted }: OtpScreenProps) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState<{ seconds: number; id: number } | null>(null);

  useIdleTimer(!busy, idleSeconds, onBack);
  const waitLeft = useCountdown(cooldown?.seconds ?? null, cooldown?.id);
  const cooling = cooldown !== null && (waitLeft ?? 0) > 0;

  // When the wait is over, take the "too many tries" message away.
  useEffect(() => {
    if (cooldown !== null && waitLeft === 0) {
      setCooldown(null);
      setMessage(null);
    }
  }, [cooldown, waitLeft]);

  const submit = async (digits: string) => {
    setBusy(true);
    setMessage(null);
    try {
      onStarted(await kioskFetch<OtpStartOut>('/api/kiosk/otp-start', { method: 'POST', body: { otp: digits } }));
    } catch (error) {
      setCode('');
      setBusy(false);
      if (error instanceof ApiError && error.code === 'OTP_COOLDOWN') {
        const seconds = typeof error.details?.retry_after_seconds === 'number' ? error.details.retry_after_seconds : 120;
        setCooldown({ seconds, id: Date.now() });
      } else if (error instanceof ApiError) {
        setMessage(error.isOffline ? 'Cannot reach the server. Please try again in a moment.' : otpFailureMessage(error));
      } else {
        setMessage('Something went wrong. Please try again.');
      }
    }
  };

  const onKey = (key: PadKey) => {
    if (busy || cooling) return;
    const next = pressKey(code, key);
    setCode(next);
    setMessage(null);
    if (isComplete(next)) void submit(next);
  };

  return (
    <div className="flex h-full items-center justify-center gap-8 px-6 min-[1200px]:gap-16 min-[1200px]:px-10">
      <section className="max-w-[34rem] space-y-6 min-[1200px]:space-y-8">
        <div className="space-y-2">
          <h1 className="text-5xl font-extrabold">Enter your code</h1>
          <p className="text-xl text-muted">The 6-digit code from your booking in the ChargeSpot app.</p>
        </div>

        <div className="flex gap-3" role="group" aria-label={`Code, ${code.length} of ${CODE_LENGTH} digits typed`}>
          {Array.from({ length: CODE_LENGTH }, (_, i) => (
            <span
              key={i}
              className={cx(
                'num flex h-16 w-14 items-center justify-center rounded-card border-2 bg-surface text-4xl font-extrabold min-[1200px]:h-24 min-[1200px]:w-20 min-[1200px]:text-5xl',
                i === code.length && !cooling ? 'border-info' : 'border-field-border',
              )}
            >
              {code[i] ?? ''}
            </span>
          ))}
        </div>

        <div aria-live="assertive" className="min-h-16 text-2xl font-bold min-[1200px]:min-h-20">
          {cooling ? (
            <p className="text-warning">
              Too many tries. Please wait <span className="num">{clockMinutes(waitLeft ?? 0)}</span>
            </p>
          ) : busy ? (
            <p className="text-muted">Checking your code…</p>
          ) : message ? (
            <p className="text-danger-soft">{message}</p>
          ) : null}
        </div>

        <KioskButton variant="secondary" icon={<ArrowLeft className="size-7" aria-hidden="true" />} onClick={onBack}>
          Back
        </KioskButton>
      </section>

      <Keypad onKey={onKey} disabled={busy || cooling} />
    </div>
  );
}
