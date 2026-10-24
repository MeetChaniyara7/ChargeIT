// "Your session ended": remembered across the redirect to Sign in, so the page can say why you are there.
// sessionStorage can be blocked (private mode), so every access is guarded and the notice is simply skipped then.

const KEY = 'chargespot.session-expired';

export function markSessionExpired(): void {
  try {
    sessionStorage.setItem(KEY, '1');
  } catch {
    /* no notice, the redirect still happens */
  }
}

/** True when a session ended since the notice was last cleared. Reading changes nothing. */
export function hasSessionExpired(): boolean {
  try {
    return sessionStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

export function clearSessionExpired(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}
