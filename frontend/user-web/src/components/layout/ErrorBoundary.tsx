import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { TriangleAlert } from 'lucide-react';
import { buttonClasses } from '../ui/button-styles';

interface State {
  failed: boolean;
}

/**
 * The last safety net: if a screen crashes while drawing, show this page instead of a blank one.
 * (React only allows error boundaries as classes.) It uses plain links so it still works if the router is what broke.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('A screen crashed:', error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 px-6 text-center">
        <TriangleAlert className="size-12 text-warning" aria-hidden="true" />
        <h1 className="text-display font-bold">Something went wrong</h1>
        <p className="text-muted">The page hit a problem it could not recover from. Nothing you paid for or booked has been changed. Reloading usually fixes it.</p>
        <div className="flex flex-wrap justify-center gap-3">
          <button type="button" className={buttonClasses({ size: 'lg' })} onClick={() => window.location.reload()}>
            Reload
          </button>
          <a href="/" className={buttonClasses({ size: 'lg', variant: 'secondary' })}>
            Go home
          </a>
        </div>
      </main>
    );
  }
}
