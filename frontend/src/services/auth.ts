import type { UserProfile } from '../types/auth';

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export const authService = {
  getToken(): string | null {
    return localStorage.getItem('token');
  },

  setToken(token: string): void {
    localStorage.setItem('token', token);
  },

  removeToken(): void {
    localStorage.removeItem('token');
  },

  async register(fullName: string, email: string, password: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name: fullName, email, password }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to create account.');
    }

    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Invalid email or password.');
    }

    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  },

  async loginWithGoogleCredential(credential: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to authenticate with Google.');
    }

    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  },

  async getCurrentUser(): Promise<UserProfile> {
    const token = this.getToken();
    if (!token) {
      throw new Error('No authentication token found.');
    }

    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();
    if (!response.ok) {
      this.removeToken();
      throw new Error(data.detail || 'Failed to fetch authenticated user profile.');
    }

    return data;
  },

  loginWithGoogle(): void {
    window.location.href = `${API_BASE_URL}/auth/google/login`;
  },

  logout(): void {
    this.removeToken();
  },
};
