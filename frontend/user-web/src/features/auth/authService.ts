import { API_URL, apiFetch, tokenStorage } from '../../lib/api';
import type { UserProfile } from './types';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

async function signIn(path: string, body: unknown): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>(path, { method: 'POST', body });
  if (data.access_token) {
    tokenStorage.set(data.access_token);
  }
  return data;
}

export const authService = {
  getToken: tokenStorage.get,
  setToken: tokenStorage.set,
  removeToken: tokenStorage.clear,

  register(fullName: string, email: string, password: string): Promise<AuthResponse> {
    return signIn('/auth/register', { full_name: fullName, email, password });
  },

  login(email: string, password: string): Promise<AuthResponse> {
    return signIn('/auth/login', { email, password });
  },

  loginWithGoogleCredential(credential: string): Promise<AuthResponse> {
    return signIn('/api/auth/google', { credential });
  },

  async getCurrentUser(): Promise<UserProfile> {
    if (!tokenStorage.get()) {
      throw new Error('No authentication token found.');
    }
    try {
      return await apiFetch<UserProfile>('/auth/me');
    } catch (err) {
      tokenStorage.clear();
      throw err;
    }
  },

  // Google redirect flow: the API sends the browser to Google and back to /login#token=...
  loginWithGoogle(): void {
    window.location.href = `${API_URL}/auth/google/login`;
  },

  logout(): void {
    tokenStorage.clear();
  },
};
