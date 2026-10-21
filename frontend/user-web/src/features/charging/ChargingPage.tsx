import React from 'react';
import { Link, Navigate } from 'react-router-dom';
import { BatteryCharging } from 'lucide-react';
import { buttonClasses, EmptyState, SkeletonBlock } from '../../components/ui';
import { useActiveSession } from './activeSessionContext';

/**
 * The Charging tab. While the driver is charging it opens that session; otherwise it says there is
 * nothing running and points to the map.
 */
export const ChargingPage: React.FC = () => {
  const { active, loading } = useActiveSession();

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-6" role="status">
        <span className="sr-only">Checking for a charging session…</span>
        <SkeletonBlock className="h-64" />
      </div>
    );
  }
  if (active) return <Navigate to={`/charging/${active.session_id}`} replace />;

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <h1 className="text-display font-bold">Charging</h1>
      <EmptyState
        icon={<BatteryCharging className="size-7" />}
        title="No charging right now"
        text="When you start charging at a station, live progress shows here: battery level, energy and cost."
        action={
          <Link to="/explore" className={buttonClasses()}>
            Find a charger
          </Link>
        }
      />
    </div>
  );
};
