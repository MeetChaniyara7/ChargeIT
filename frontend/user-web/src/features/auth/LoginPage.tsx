import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { LoginForm } from './LoginForm';

export const LoginPage: React.FC = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return null; // AuthContext handles loading state or smooth transition
  }

  // Redirect to dashboard if already logged in
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-[calc(100vh-80px)] flex items-center justify-center p-4">
      <LoginForm />
    </div>
  );
};
