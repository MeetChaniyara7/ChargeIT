/** Where signed-in users land when they didn't come from a specific page. */
export const DEFAULT_AFTER_LOGIN = '/explore';

const AUTH_PAGES = ['/login', '/register'];

/**
 * Where to send the user after signing in: the protected page they were trying to open
 * (ProtectedRoute passes it as `state.from`, including any ?query), else Explore.
 * Only same-site paths are accepted.
 */
export function returnPathFrom(state: unknown): string {
  const from = (state as { from?: { pathname?: string; search?: string } } | null)?.from;
  const path = from?.pathname;
  if (path && path.startsWith('/') && !path.startsWith('//') && !AUTH_PAGES.includes(path)) {
    return path + (from?.search ?? '');
  }
  return DEFAULT_AFTER_LOGIN;
}
