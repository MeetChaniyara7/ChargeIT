import { NavLink, Outlet } from 'react-router-dom';
import { BatteryCharging, Map, Ticket, User } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '../../features/auth/AuthContext';
import { initialsOf } from '../../features/auth/initials';
import { cx } from '../ui';
import { Footer } from './Footer';
import { Logo } from './Logo';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

// The four places a signed-in driver goes. Same items in the top bar (desktop)
// and the bottom tab bar (phone).
const NAV: NavItem[] = [
  { to: '/explore', label: 'Explore', icon: Map },
  { to: '/bookings', label: 'Bookings', icon: Ticket },
  { to: '/charging', label: 'Charging', icon: BatteryCharging },
  { to: '/profile', label: 'Profile', icon: User },
];

/**
 * The frame for signed-in pages.
 * Desktop: slim top bar. Phone: slim logo bar on top and a tab bar at the bottom
 * (with room for the phone's home indicator).
 */
export function AppLayout() {
  const { user } = useAuth();

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-primary focus:px-3 focus:py-2 focus:text-on-primary">
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b border-border bg-bg">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 lg:px-8">
          <Logo to="/explore" />

          <nav aria-label="Main" className="ml-4 hidden items-center gap-1 md:flex">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cx(
                    'inline-flex min-h-11 items-center gap-2 rounded-control px-3 text-sm font-bold transition-colors',
                    isActive ? 'bg-raised text-fg' : 'text-muted hover:bg-raised hover:text-fg',
                  )
                }
              >
                <Icon className="size-4" aria-hidden="true" />
                {label}
              </NavLink>
            ))}
          </nav>

          <NavLink
            to="/profile"
            aria-label="Your profile"
            className="ml-auto flex size-11 items-center justify-center rounded-full bg-raised text-sm font-bold md:hidden"
          >
            {initialsOf(user?.full_name, user?.email)}
          </NavLink>
        </div>
      </header>

      {/* Bottom padding keeps content clear of the phone tab bar. */}
      <div className="flex flex-1 flex-col pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
        <main id="main" className="flex-1">
          <Outlet />
        </main>
        <Footer />
      </div>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <ul className="mx-auto flex h-16 max-w-md items-stretch">
          {NAV.map(({ to, label, icon: Icon }) => (
            <li key={to} className="flex-1">
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cx(
                    'flex h-full flex-col items-center justify-center gap-1 text-xs font-bold transition-colors',
                    isActive ? 'text-primary' : 'text-muted',
                  )
                }
              >
                <Icon className="size-6" aria-hidden="true" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
