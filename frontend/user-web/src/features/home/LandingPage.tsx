import React, { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Gauge, Receipt, Search, ShieldCheck } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { Button, buttonClasses, Card, SkeletonLine, TextInput } from '../../components/ui';
import { useAuth } from '../auth/AuthContext';
import { BookIllustration, ChargeIllustration, CodeIllustration, FindIllustration } from './illustrations';

const STEPS = [
  { title: 'Find', text: 'See charging stations near you and which chargers are free.', Illustration: FindIllustration },
  { title: 'Book', text: 'Pick a 30-minute slot, like choosing a seat at the cinema.', Illustration: BookIllustration },
  { title: 'Enter code', text: 'Type your one-time code on the screen at the station.', Illustration: CodeIllustration },
  { title: 'Charge', text: 'Plug in, watch progress on your phone, pay in the app.', Illustration: ChargeIllustration },
];

const REASONS = [
  {
    icon: ShieldCheck,
    title: 'No double bookings',
    text: 'The database itself refuses two bookings for the same charger and time, even if two people tap at once.',
  },
  {
    icon: Gauge,
    title: 'Know before you go',
    text: 'Plug type, power and price up front. Values we had to estimate are labelled "Approximate".',
  },
  {
    icon: Receipt,
    title: 'Pay in the app',
    text: 'A ₹199 booking fee holds your slot. You pay for the energy you used after charging.',
  },
];

type StationCount = { state: 'loading' } | { state: 'ready'; count: number } | { state: 'error' };

/** How many stations are on the map, from the live API (the line is hidden if that fails). */
function useStationCount(): StationCount {
  const [result, setResult] = useState<StationCount>({ state: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<{ count: number }>('/api/stations/count', { signal: controller.signal })
      .then(({ count }) => setResult(typeof count === 'number' ? { state: 'ready', count } : { state: 'error' }))
      .catch((err) => {
        if (!(err instanceof DOMException && err.name === 'AbortError')) setResult({ state: 'error' });
      });
    return () => controller.abort();
  }, []);

  return result;
}

export const LandingPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const stations = useStationCount();

  // Signed-in drivers have no use for the sales page.
  if (user) return <Navigate to="/explore" replace />;

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    // Explore needs an account; the sign-in page sends people back here afterwards.
    navigate(q ? `/explore?q=${encodeURIComponent(q)}` : '/explore');
  };

  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-3xl px-4 pb-12 pt-12 text-center md:pt-20">
        <h1 className="text-display font-bold leading-tight tracking-tight md:text-hero">
          Book your EV charger before you arrive
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-base text-muted">
          Find charging stations, see which chargers are free, reserve a slot and start charging with a one-time code.
        </p>

        <form role="search" onSubmit={onSearch} className="mx-auto mt-8 flex max-w-xl flex-col gap-3 sm:flex-row">
          <label htmlFor="landing-search" className="sr-only">
            Search for a place or station
          </label>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted" aria-hidden="true" />
            <TextInput
              id="landing-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Where do you want to charge?"
              className="min-h-12 pl-10"
            />
          </div>
          <Button type="submit" size="lg">
            Find chargers
          </Button>
        </form>

        <div className="mt-4 flex h-5 items-center justify-center text-sm text-muted" aria-live="polite">
          {stations.state === 'loading' && <SkeletonLine className="h-4 w-56" />}
          {stations.state === 'ready' && stations.count > 0 && (
            <span>
              <span className="num font-bold text-fg">{stations.count}</span> charging stations across Gujarat
            </span>
          )}
        </div>
      </section>

      {/* How it works */}
      <section aria-labelledby="how-heading" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-12">
          <h2 id="how-heading" className="text-center text-xl font-bold">
            How it works
          </h2>
          <ol className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ title, text, Illustration }, index) => (
              <li key={title} className="flex flex-col items-center text-center">
                <Illustration />
                <p className="mt-3 text-sm font-bold text-primary">Step {index + 1}</p>
                <h3 className="text-xl font-bold">{title}</h3>
                <p className="mt-1 max-w-56 text-sm text-muted">{text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Why ChargeSpot */}
      <section aria-labelledby="why-heading" className="mx-auto max-w-6xl px-4 py-12">
        <h2 id="why-heading" className="text-center text-xl font-bold">
          Why ChargeSpot
        </h2>
        <ul className="mt-8 grid gap-4 md:grid-cols-3">
          {REASONS.map(({ icon: Icon, title, text }) => (
            <li key={title}>
              <Card className="h-full p-5">
                <Icon className="size-6 text-primary" aria-hidden="true" />
                <h3 className="mt-3 text-base font-bold">{title}</h3>
                <p className="mt-1 text-sm text-muted">{text}</p>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      {/* Call to action */}
      <section className="mx-auto max-w-3xl px-4 pb-16 text-center">
        <Card elevation={2} className="p-8">
          <h2 className="text-xl font-bold">Ready to skip the wait?</h2>
          <p className="mt-1 text-sm text-muted">Sign in with Google to see chargers near you.</p>
          <Link to="/login" className={`${buttonClasses({ size: 'lg' })} mt-5`}>
            Sign in with Google
          </Link>
        </Card>
      </section>
    </div>
  );
};
