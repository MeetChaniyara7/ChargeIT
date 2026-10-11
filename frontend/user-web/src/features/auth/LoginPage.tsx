import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { LoginForm } from './LoginForm';
import { returnPathFrom } from './returnTo';

export const LoginPage: React.FC = () => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return null; // AuthContext handles loading state or smooth transition
  }

  // Already signed in: go back to where the user was heading (or Explore).
  if (user) {
    return <Navigate to={returnPathFrom(location.state)} replace />;
  }

  return (
    <div className="flex items-center justify-center px-4 py-10 md:py-16">
      <LoginForm />
    </div>
  );
};
