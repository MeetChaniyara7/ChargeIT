import type { ReactNode } from 'react';
import { Card } from './Card';

export interface StatTileProps {
  label: string;
  value: ReactNode;
  /** A small line under the number, e.g. "last 30 days". */
  hint?: string;
}

/** One number with its label: the building block of the admin overview. */
export function StatTile({ label, value, hint }: StatTileProps) {
  return (
    <Card className="p-4">
      <dl>
        <dt className="text-sm text-muted">{label}</dt>
        <dd className="num mt-1 text-display font-bold leading-tight">{value}</dd>
        {hint && <dd className="mt-0.5 text-xs text-muted">{hint}</dd>}
      </dl>
    </Card>
  );
}
