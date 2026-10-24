import React from 'react';
import { Link, NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom';
import { ArrowLeft, Bell, Building2, CalendarClock, Gauge, History, LogOut, MapPin, MonitorSmartphone, Users, Wallet, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cx } from '../../components/ui';
import { Logo } from '../../components/layout/Logo';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { useAuth } from '../auth/AuthContext';
import { initialsOf } from '../auth/initials';
import type { Alert } from './types';

interface Item {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

// Grouped the way an admin thinks: the network, the money, the people, the system.
const GROUPS: { title: string; items: Item[] }[] = [
  { title: 'Overview', items: [{ to: '/admin', label: 'Overview', icon: Gauge, end: true }] },
  {
    title: 'Network',
    items: [
      { to: '/admin/stations', label: 'Stations', icon: MapPin },
      { to: '/admin/operators', label: 'Operators', icon: Building2 },
      { to: '/admin/kiosks', label: 'Kiosks', icon: MonitorSmartphone },
      { to: '/admin/simulator', label: 'Simulator', icon: Zap },
    ],
  },
  {
    title: 'Business',
    items: [
      { to: '/admin/bookings', label: 'Bookings', icon: CalendarClock },
      { to: '/admin/payments', label: 'Payments', icon: Wallet },
    ],
  },
  { title: 'People', items: [{ to: '/admin/users', label: 'Users and roles', icon: Users }] },
  {
    title: 'System',
    items: [
      { to: '/admin/alerts', label: 'Alerts', icon: Bell },
      { to: '/admin/activity', label: 'Activity log', icon: History },
    ],
  },
];

/**
 * Only admins get in. This is a convenience (everyone else is sent to Explore): the server checks the role on every
 * admin request, so hiding the page is not what keeps the data safe.
 */
export const RequireAdmin: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  if (user?.role !== 'ADMIN') return <Navigate to="/explore" replace />;
  return <>{children}</>;
};

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cx(
    'flex min-h-11 items-center gap-2 rounded-control px-3 text-sm font-bold transition-colors duration-150',
    isActive ? 'bg-raised text-primary' : 'text-muted hover:bg-raised hover:text-fg',
  );

/**
 * The admin's own screen: its own header and sidebar, none of the driver tabs. Left menu on desktop, a scrolling row of
 * tabs on a phone. Plain and data-dense.
 */
export const AdminLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const alerts = useApiQuery('/api/admin/alerts', (signal) => apiFetch<Alert[]>('/api/admin/alerts', { signal }));
  const open = alerts.data?.length ?? 0;
  const badge = (label: string) =>
    label === 'Alerts' && open > 0 ? (
      <span className="num ml-auto rounded-full bg-danger-strong px-1.5 text-xs text-white" aria-label={`${open} open alerts`}>
        {open}
      </span>
    ) : null;

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#admin-main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-primary focus:px-3 focus:py-2 focus:text-on-primary">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-bg">
        <div className="flex h-14 items-center gap-2 px-4 sm:gap-3 lg:px-6">
          <Logo to="/admin" />
          <span className="rounded-control bg-primary/15 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-primary">Admin</span>
          <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-2">
            <Link to="/explore" className="inline-flex min-h-11 items-center gap-1.5 rounded-control px-3 text-sm font-bold text-muted hover:bg-raised hover:text-fg">
              <ArrowLeft className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Back to the app</span>
              <span className="sm:hidden">App</span>
            </Link>
            <span className="hidden text-sm text-muted md:inline" title={user?.email}>
              {user?.full_name || user?.email}
            </span>
            <span className="hidden size-9 items-center justify-center rounded-full bg-raised text-xs font-bold sm:flex" aria-hidden="true">
              {initialsOf(user?.full_name, user?.email)}
            </span>
            <button
              type="button"
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="inline-flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-control px-2 text-sm font-bold text-muted hover:bg-raised hover:text-fg sm:px-3"
            >
              <LogOut className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
              <span className="sr-only sm:hidden">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[90rem] flex-1 flex-col gap-4 px-4 py-4 md:flex-row md:gap-8 md:py-6 lg:px-6">
        <nav aria-label="Admin" className="md:w-56 md:shrink-0">
          {/* Phone: one scrolling row of tabs. Desktop: grouped list. */}
          <ul className="scroll-x-hidden -mx-4 flex gap-1 overflow-x-auto px-4 md:hidden">
            {GROUPS.flatMap((g) => g.items).map(({ to, label, icon: Icon, end }) => (
              <li key={to} className="shrink-0">
                <NavLink to={to} end={end} className={linkClass}>
                  <Icon className="size-4" aria-hidden="true" />
                  {label}
                  {badge(label)}
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="hidden space-y-4 md:block md:sticky md:top-20">
            {GROUPS.map((group) => (
              <div key={group.title}>
                {group.items.length > 1 || group.title !== group.items[0].label ? (
                  <p className="mb-1 px-3 text-xs font-bold uppercase tracking-wide text-muted">{group.title}</p>
                ) : null}
                <ul className="flex flex-col gap-0.5">
                  {group.items.map(({ to, label, icon: Icon, end }) => (
                    <li key={to}>
                      <NavLink to={to} end={end} className={linkClass}>
                        <Icon className="size-4" aria-hidden="true" />
                        {label}
                        {badge(label)}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </nav>
        <main id="admin-main" className="min-w-0 flex-1 space-y-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
