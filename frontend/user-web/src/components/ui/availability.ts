export type Availability = 'free' | 'few' | 'busy' | 'offline';

/** Free / Few left / Busy / Offline for a number of free chargers out of a total. */
export function availabilityFor(free: number, total: number): Availability {
  if (total <= 0) return 'offline';
  if (free <= 0) return 'busy';
  return free === 1 || free / total <= 0.25 ? 'few' : 'free';
}
