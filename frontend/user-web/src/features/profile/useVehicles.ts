import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import type { VehicleOut } from '../bookings/types';

/** The signed-in user's vehicles (default first). `retry()` reloads them after a change. */
export function useVehicles() {
  const query = useApiQuery('/api/me/vehicles', (signal) => apiFetch<VehicleOut[]>('/api/me/vehicles', { signal }));
  const vehicles = query.data ?? [];
  return { ...query, vehicles, defaultVehicle: vehicles.find((v) => v.is_default) ?? null };
}
