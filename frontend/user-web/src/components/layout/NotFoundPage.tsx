import { Link } from 'react-router-dom';
import { MapPinOff } from 'lucide-react';
import { buttonClasses } from '../ui';

/** Shown for any address that does not exist. */
export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-6 py-20 text-center">
      <MapPinOff className="size-12 text-muted" aria-hidden="true" />
      <h1 className="text-display font-bold">Page not found</h1>
      <p className="text-muted">We could not find that page. It may have moved, or the address may have a typo.</p>
      <div className="flex flex-wrap justify-center gap-3">
        <Link to="/explore" className={buttonClasses({ size: 'lg' })}>
          Find a charger
        </Link>
        <Link to="/" className={buttonClasses({ size: 'lg', variant: 'secondary' })}>
          Go home
        </Link>
      </div>
    </div>
  );
}
