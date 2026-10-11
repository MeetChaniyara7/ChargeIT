import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Car, ChevronRight, LogOut } from 'lucide-react';
import { Badge, Button, Card } from '../../components/ui';
import { useAuth } from '../auth/AuthContext';
import { initialsOf } from '../auth/initials';

export const ProfilePage: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const signOut = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <h1 className="text-display font-bold">Profile</h1>

      <Card className="mt-4 flex items-center gap-4 p-4">
        <div className="flex size-14 shrink-0 items-center justify-center rounded-full bg-raised text-xl font-bold" aria-hidden="true">
          {initialsOf(user?.full_name, user?.email)}
        </div>
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-base font-bold">
            <span className="truncate">{user?.full_name || 'ChargeSpot driver'}</span>
            {user?.role === 'ADMIN' && <Badge tone="info">Admin</Badge>}
          </p>
          <p className="truncate text-sm text-muted">{user?.email}</p>
        </div>
      </Card>

      <Card className="mt-4">
        <Link
          to="/profile/vehicles"
          className="flex min-h-14 items-center gap-3 rounded-card px-4 hover:bg-raised"
        >
          <Car className="size-5 text-muted" aria-hidden="true" />
          <span className="flex-1 font-medium">My vehicles</span>
          <ChevronRight className="size-5 text-muted" aria-hidden="true" />
        </Link>
      </Card>

      <Button variant="secondary" fullWidth className="mt-6" icon={<LogOut className="size-4" aria-hidden="true" />} onClick={signOut}>
        Sign out
      </Button>
    </div>
  );
};
