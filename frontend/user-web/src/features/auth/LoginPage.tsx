import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { LoginForm } from './LoginForm';
import { returnPathFrom } from './returnTo';
import { clearSessionExpired, hasSessionExpired } from './sessionNotice';

export const LoginPage: React.FC = () => {
  const { user, loading } = useAuth();
  const location = useLocation();
  const [expired] = useState(hasSessionExpired);
  useEffect(() => clearSessionExpired, []); // said once: the next visit starts clean

  if (loading) {
    return null; // AuthContext handles loading state or smooth transition
  }

  // Already signed in: go back to where the user was heading (or Explore).
  if (user) {
    return <Navigate to={returnPathFrom(location.state)} replace />;
  }

  return (
    <div className="flex flex-col items-center justify-center gap-4 px-4 py-10 md:py-16">
      {expired && (
        <p role="status" className="w-full max-w-md rounded-card border border-warning/40 bg-warning/10 p-3 text-sm">
          Your session ended, so we signed you out to keep your account safe. Sign in again and you will come straight back to where you were.
        </p>
      )}
      <LoginForm />
    </div>
  );
};
