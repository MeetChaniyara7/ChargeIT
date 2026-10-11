import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { Button, Card, Field, TextInput } from '../../components/ui';
import { useAuth } from './AuthContext';
import { GoogleSignInButton } from './GoogleSignInButton';
import { returnPathFrom } from './returnTo';

interface FieldErrors {
  email?: string;
  password?: string;
}

export const LoginForm: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const goAfterLogin = () => navigate(returnPathFrom(location.state), { replace: true });

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const errors: FieldErrors = {};
    if (!email.trim()) errors.email = 'Enter your email address.';
    else if (!/\S+@\S+\.\S+/.test(email)) errors.email = 'Enter a valid email address.';
    if (!password) errors.password = 'Enter your password.';
    setFieldErrors(errors);
    if (errors.email || errors.password) return;

    setLoading(true);
    try {
      const { error: loginError } = await login(email, password);
      if (loginError) setError(loginError);
      else goAfterLogin();
    } catch {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card elevation={2} className="w-full max-w-sm p-6">
      <h1 className="text-xl font-bold">Welcome back</h1>
      <p className="mt-1 text-sm text-muted">Sign in to find and book a charger.</p>

      {error && (
        <div role="alert" className="mt-4 flex items-start gap-2 rounded-control border border-danger/30 bg-danger/10 p-3 text-sm text-danger-soft">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <div className="mt-5">
        <GoogleSignInButton onSuccess={goAfterLogin} onError={setError} onBusyChange={setLoading} />
      </div>

      <div className="my-5 flex items-center gap-3 text-xs text-muted" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />
        or use email
        <span className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field label="Email address" error={fieldErrors.email}>
          {(p) => (
            <TextInput {...p} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          )}
        </Field>
        <Field label="Password" error={fieldErrors.password}>
          {(p) => (
            <TextInput {...p} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          )}
        </Field>
        <Button type="submit" fullWidth loading={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>

      <p className="mt-6 border-t border-border pt-4 text-center text-sm text-muted">
        New to ChargeSpot?{' '}
        <Link to="/register" state={location.state} className="font-bold text-info underline-offset-2 hover:underline">
          Create an account
        </Link>
      </p>
    </Card>
  );
};
