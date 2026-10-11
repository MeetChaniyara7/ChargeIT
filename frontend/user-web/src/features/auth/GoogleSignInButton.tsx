import React, { useEffect, useRef, useState } from 'react';
import { Button } from '../../components/ui';
import { useAuth } from './AuthContext';

// Minimal typing for the parts of Google Identity Services we use.
interface GoogleIdentity {
  accounts: {
    id: {
      initialize: (config: { client_id: string; callback: (response: { credential?: string }) => void }) => void;
      renderButton: (element: HTMLElement, options: Record<string, unknown>) => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

const googleClientId: string | undefined = import.meta.env.VITE_GOOGLE_CLIENT_ID;

// The Google script (index.html) loads asynchronously, so it may not be ready when the
// form first appears. Check again every 250 ms for up to 10 seconds.
const POLL_MS = 250;
const MAX_POLLS = 40;

interface GoogleSignInButtonProps {
  /** Called after Google sign-in succeeded and the user is signed in. */
  onSuccess: () => void;
  /** Called with a message to show when Google sign-in failed. */
  onError: (message: string) => void;
  onBusyChange?: (busy: boolean) => void;
}

/**
 * "Continue with Google". Uses Google's own button when its script is available.
 * Otherwise (script blocked, or still loading) a plain button starts the redirect flow.
 */
export const GoogleSignInButton: React.FC<GoogleSignInButtonProps> = ({ onSuccess, onError, onBusyChange }) => {
  const { loginWithGoogle, loginWithGoogleCredential } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const [googleReady, setGoogleReady] = useState(false);

  // Always call the latest handlers without re-initialising Google's button.
  const handlers = useRef({ onSuccess, onError, onBusyChange, loginWithGoogleCredential });
  useEffect(() => {
    handlers.current = { onSuccess, onError, onBusyChange, loginWithGoogleCredential };
  });

  useEffect(() => {
    if (!googleClientId) return;
    let timer: number | undefined;
    let cancelled = false;
    let polls = 0;

    const tryInit = () => {
      if (cancelled) return;
      const container = containerRef.current;
      const google = window.google;
      if (google?.accounts?.id && container) {
        try {
          google.accounts.id.initialize({
            client_id: googleClientId,
            callback: async (response) => {
              if (!response.credential) return;
              handlers.current.onBusyChange?.(true);
              const { error } = await handlers.current.loginWithGoogleCredential(response.credential);
              handlers.current.onBusyChange?.(false);
              if (error) handlers.current.onError(error);
              else handlers.current.onSuccess();
            },
          });
          google.accounts.id.renderButton(container, {
            theme: 'filled_black',
            size: 'large',
            shape: 'rectangular',
            text: 'continue_with',
            width: Math.min(320, container.clientWidth || 320),
          });
          setGoogleReady(true);
        } catch (err) {
          console.warn('Google Identity Services could not start:', err);
        }
        return;
      }
      if (polls++ < MAX_POLLS) timer = window.setTimeout(tryInit, POLL_MS);
    };

    tryInit();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  return (
    <div className="flex w-full flex-col items-center">
      <div ref={containerRef} className={googleReady ? 'flex min-h-11 w-full justify-center' : 'hidden'} />
      {!googleReady && (
        <Button variant="secondary" fullWidth onClick={loginWithGoogle} icon={<GoogleMark />}>
          Continue with Google
        </Button>
      )}
    </div>
  );
};

/** The multicolour Google "G" (brand colours are part of Google's required look). */
const GoogleMark: React.FC = () => (
  <svg className="size-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
  </svg>
);
