export type Availability = 'free' | 'few' | 'busy' | 'offline';

/**
 * Free / Few left / Busy / Offline for a number of free chargers out of a total.
 * Map pins and status badges both use this, so they always agree:
 * 2 or more free = green, exactly 1 = amber, none = rose, no chargers = grey.
 */
export function availabilityFor(free: number, total: number): Availability {
  if (total <= 0) return 'offline';
  if (free >= 2) return 'free';
  if (free === 1) return 'few';
  return 'busy';
}
