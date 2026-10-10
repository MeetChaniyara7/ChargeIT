// One place for every call to the ChargeSpot API.
// - Adds the login token (Authorization: Bearer ...) when the user is signed in.
// - Turns the API's error format {"error": {"code", "message"}} into an ApiError.
// - On 401 (token missing/expired) clears the stored token and tells the app to sign out.

const configuredUrl: string | undefined = import.meta.env.VITE_API_URL;
if (!configuredUrl) {
  throw new Error('VITE_API_URL is not set. Copy frontend/user-web/.env.example to .env and fill it in.');
}
export const API_URL = configuredUrl.replace(/\/+$/, '');

const TOKEN_KEY = 'token';
export const UNAUTHORIZED_EVENT = 'chargespot:unauthorized';

export const tokenStorage = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string): void => localStorage.setItem(TOKEN_KEY, token),
  clear: (): void => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  const token = tokenStorage.get();
  if (token) headers['Authorization'] = `Bearer ${token}`;

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
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the ChargeSpot server. Check your connection.');
  }

  const data: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401 && token) {
      tokenStorage.clear();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    const error = (data as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? `HTTP_${response.status}`,
      error?.message ?? `Request failed (HTTP ${response.status}).`,
    );
  }

  return data as T;
}
