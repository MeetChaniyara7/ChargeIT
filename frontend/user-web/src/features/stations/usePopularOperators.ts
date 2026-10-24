import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import type { OperatorChip } from './types';

/** The brands with the most stations, for the "Brand" filter row. If it fails the row simply stays empty. */
export function usePopularOperators(): OperatorChip[] {
  const query = useApiQuery('/api/search/operators', (signal) => apiFetch<OperatorChip[]>('/api/search/operators', { signal }));
  return query.data ?? [];
}
