import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button, Card, Field, TextInput } from '../../components/ui';
import { useAuth } from './AuthContext';
import { GoogleSignInButton } from './GoogleSignInButton';
import { returnPathFrom } from './returnTo';

interface FieldErrors {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

export const RegisterForm: React.FC = () => {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const goAfterSignup = () => navigate(returnPathFrom(location.state), { replace: true });

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // The short "Account created" pause before redirecting must not fire after leaving the page.
  const redirectTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(redirectTimer.current), []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    const errors: FieldErrors = {};
    if (!fullName.trim()) errors.fullName = 'Enter your name.';
    if (!email.trim()) errors.email = 'Enter your email address.';
    else if (!/\S+@\S+\.\S+/.test(email)) errors.email = 'Enter a valid email address.';
    if (!password) errors.password = 'Choose a password.';
    else if (password.length < 6) errors.password = 'Use at least 6 characters.';
    if (!confirmPassword) errors.confirmPassword = 'Type your password again.';
    else if (password !== confirmPassword) errors.confirmPassword = 'Passwords do not match.';
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setLoading(true);
    try {
      const { error: signUpError } = await signUp(email, password, fullName);
      if (signUpError) {
        setError(signUpError);
      } else {
        setSuccessMsg('Account created. Taking you to the map…');
        redirectTimer.current = window.setTimeout(goAfterSignup, 1500);
      }
    } catch {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card elevation={2} className="w-full max-w-sm p-6">
      <h1 className="text-xl font-bold">Create your account</h1>
      <p className="mt-1 text-sm text-muted">It takes a minute. Then find a charger near you.</p>

      {error && (
        <div role="alert" className="mt-4 flex items-start gap-2 rounded-control border border-danger/30 bg-danger/10 p-3 text-sm text-danger-soft">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
      {successMsg && (
        <div role="status" className="mt-4 flex items-start gap-2 rounded-control border border-primary/30 bg-primary/10 p-3 text-sm text-primary">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{successMsg}</span>
        </div>
      )}

      <div className="mt-5">
        <GoogleSignInButton onSuccess={goAfterSignup} onError={setError} onBusyChange={setLoading} />
      </div>

      <div className="my-5 flex items-center gap-3 text-xs text-muted" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />
        or use email
        <span className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field label="Full name" error={fieldErrors.fullName}>
          {(p) => <TextInput {...p} type="text" autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} />}
        </Field>
        <Field label="Email address" error={fieldErrors.email}>
          {(p) => (
            <TextInput {...p} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          )}
        </Field>
        <Field label="Password" hint="At least 6 characters." error={fieldErrors.password}>
          {(p) => <TextInput {...p} type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label="Confirm password" error={fieldErrors.confirmPassword}>
          {(p) => (
            <TextInput {...p} type="password" autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
          )}
        </Field>
        <Button type="submit" fullWidth loading={loading} disabled={Boolean(successMsg)}>
          {loading ? 'Creating account…' : 'Create account'}
        </Button>
      </form>

      <p className="mt-6 border-t border-border pt-4 text-center text-sm text-muted">
        Already have an account?{' '}
        <Link to="/login" state={location.state} className="font-bold text-info underline-offset-2 hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  );
};
