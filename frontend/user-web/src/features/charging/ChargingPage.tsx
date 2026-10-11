import React from 'react';
import { BatteryCharging } from 'lucide-react';
import { EmptyState } from '../../components/ui';

/** Placeholder: the live charging screen arrives with charging sessions. */
export const ChargingPage: React.FC = () => (
  <div className="mx-auto max-w-2xl px-4 py-6">
    <h1 className="text-display font-bold">Charging</h1>
    <EmptyState
      icon={<BatteryCharging className="size-7" />}
      title="No charging right now"
      text="When you start charging at a station, live progress will show here."
    />
  </div>
);
