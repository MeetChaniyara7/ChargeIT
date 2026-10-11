import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { SkeletonBlock, SkeletonLine } from '../../components/ui';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/** Only lets signed-in users through; everyone else goes to Sign in and comes back afterwards. */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div role="status" className="mx-auto flex min-h-dvh max-w-2xl flex-col gap-4 p-6">
        <span className="sr-only">Restoring your session…</span>
        <SkeletonLine className="h-8 w-48" />
        <SkeletonBlock className="h-40" />
        <SkeletonBlock className="h-24" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
