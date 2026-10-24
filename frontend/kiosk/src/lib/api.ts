// One place for every call the kiosk makes to the ChargeSpot API.
// - Sends the kiosk's own key in the X-Device-Key header (the key is pasted once on the setup screen).
// - Turns the API's error format {"error": {"code", "message", "details"?}} into an ApiError.

import type { components } from '@chargespot/shared';

const configuredUrl: string | undefined = import.meta.env.VITE_API_URL;
if (!configuredUrl) {
  throw new Error('VITE_API_URL is not set. Copy frontend/kiosk/.env.example to .env and fill it in.');
}
export const API_URL = configuredUrl.replace(/\/+$/, '');

type Schemas = components['schemas'];
export type KioskStatus = Schemas['KioskStatus'];
export type ChargerTile = Schemas['ChargerTile'];
export type WalkInOption = Schemas['WalkInOption'];
export type WalkInOut = Schemas['WalkInOut'];
export type OtpStartOut = Schemas['OtpStartOut'];
export type WalkInStopOut = Schemas['WalkInStopOut'];

const KEY_STORAGE = 'chargespot.kiosk.key';

/** The key lives only on this tablet. Storage can be blocked (private mode), so every access is guarded. */
export const keyStorage = {
  get(): string | null {
    try {
      return localStorage.getItem(KEY_STORAGE);
    } catch {
      return null;
    }
  },
  set(key: string): void {
    try {
      localStorage.setItem(KEY_STORAGE, key);
    } catch {
      /* the key then lasts only until the page is reloaded */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(KEY_STORAGE);
    } catch {
      /* nothing to clear */
    }
  },
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | undefined;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** The server could not be reached (or answered with something that is not ours). */
  get isOffline(): boolean {
    return this.status === 0 || this.status >= 502;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  signal?: AbortSignal;
  /** Use this key instead of the stored one (the setup screen tries a key before saving it). */
  key?: string;
}

export async function kioskFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  const key = options.key ?? keyStorage.get();
  if (key) headers['X-Device-Key'] = key.trim();

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the ChargeSpot server.');
  }

  if (!response.ok) {
    let code = 'UNKNOWN_ERROR';
    let message = 'Something went wrong.';
    let details: Record<string, unknown> | undefined;
    try {
      const body = await response.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        details = body.error.details ?? undefined;
      }
    } catch {
      /* not JSON: keep the generic message (a gateway error page, say) */
    }
    throw new ApiError(response.status, code, message, details);
  }
  return (await response.json()) as T;
}
