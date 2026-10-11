import { Link, Outlet } from 'react-router-dom';
import { useAuth } from '../../features/auth/AuthContext';
import { Footer } from './Footer';
import { Logo } from './Logo';

/** The frame for pages anyone can see: Landing, Sign in, Sign up. */
export function PublicLayout() {
  const { user } = useAuth();

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-primary focus:px-3 focus:py-2 focus:text-on-primary">
        Skip to content
      </a>
      <header className="border-b border-border bg-bg">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <Logo />
          <Link
            to={user ? '/explore' : '/login'}
            className="inline-flex min-h-11 items-center rounded-control px-3 text-sm font-bold hover:bg-raised"
          >
            {user ? 'Open app' : 'Sign in'}
          </Link>
        </div>
      </header>
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
