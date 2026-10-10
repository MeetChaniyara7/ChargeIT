import React, { createContext, useContext, useEffect, useState } from 'react';
import { UNAUTHORIZED_EVENT } from '../../lib/api';
import type { AuthContextType, UserProfile } from './types';
import { authService } from './authService';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchCurrentUser = async () => {
    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // 1. Check for token in URL hash after Google OAuth callback redirect (#token=xxx)
    if (window.location.hash.includes('#token=')) {
      const hashParams = new URLSearchParams(window.location.hash.substring(1));
      const urlToken = hashParams.get('token');
      if (urlToken) {
        authService.setToken(urlToken);
        // Clear hash from URL cleanly
        window.history.replaceState(null, '', window.location.pathname);
      }
    }

    // 2. Fetch authenticated user if token exists
    const token = authService.getToken();
    if (token) {
      fetchCurrentUser();
    } else {
      setLoading(false);
    }

    // 3. Sign out locally whenever the API rejects our token (expired or revoked).
    const handleUnauthorized = () => setUser(null);
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  const signUp = async (email: string, password: string, fullName: string) => {
    try {
      const res = await authService.register(fullName, email, password);
      setUser(res.user);
      return { error: null };
    } catch (err: any) {
      return { error: err.message || 'Failed to create account.' };
    }
  };

  const login = async (email: string, password: string) => {
    try {
      const res = await authService.login(email, password);
      setUser(res.user);
      return { error: null };
    } catch (err: any) {
      return { error: err.message || 'Invalid email or password.' };
    }
  };

  const loginWithGoogleCredential = async (credential: string) => {
    try {
      const res = await authService.loginWithGoogleCredential(credential);
      setUser(res.user);
      return { error: null };
    } catch (err: any) {
      return { error: err.message || 'Failed to authenticate with Google.' };
    }
  };

  const loginWithGoogle = () => {
    authService.loginWithGoogle();
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: Boolean(user),
        signUp,
        login,
        loginWithGoogleCredential,
        loginWithGoogle,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
