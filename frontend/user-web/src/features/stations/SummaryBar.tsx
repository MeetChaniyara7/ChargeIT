import React from 'react';
import { X } from 'lucide-react';
import type { EnergyEstimate } from '@chargespot/shared';
import { Button, IconButton, Money } from '../../components/ui';

interface SummaryBarProps {
  chargerLabel: string;
  /** e.g. "Sat 12 Oct · 4:30–5:30 PM" */
  slot: string;
  fee: number;
  estimate: EnergyEstimate | null;
  /** Which car the estimate uses, or why it has no battery limit. */
  vehicleNote?: string;
  loading: boolean;
  disabledReason?: string;
  onConfirm: () => void;
  onClear: () => void;
}

/** Slides up from the bottom when blocks are picked. Sits above the phone's bottom tabs. */
export const SummaryBar: React.FC<SummaryBarProps> = ({ chargerLabel, slot, fee, estimate, vehicleNote, loading, disabledReason, onConfirm, onClear }) => (
  <section
    aria-label="Your booking"
    className="slide-up fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-30 border-t border-border bg-surface shadow-e3 md:bottom-0"
  >
    <div className="mx-auto flex max-w-4xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate text-base font-bold">
          {chargerLabel} <span className="font-medium text-muted">·</span> <span className="num">{slot}</span>
        </p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-4 gap-y-0.5 text-sm text-muted">
          <span>
            Booking fee <Money value={fee} className="font-bold text-fg" />
          </span>
          <span>
            {estimate ? (
              <>
                Est. charging <Money value={estimate.cost} className="font-bold text-fg" />{' '}
                <span className="text-xs">(estimate{estimate.limitedByBattery ? ', battery full' : ''})</span>
              </>
            ) : (
              <>Est. charging: price or power unknown</>
            )}
          </span>
        </p>
        {vehicleNote && <p className="text-xs text-muted">{vehicleNote}</p>}
        {disabledReason && <p className="mt-1 text-xs font-medium text-warning">{disabledReason}</p>}
      </div>
      <div className="flex items-center gap-2">
        <IconButton aria-label="Clear my pick" onClick={onClear} variant="secondary">
          <X className="size-5" aria-hidden="true" />
        </IconButton>
        <Button size="lg" loading={loading} disabled={!!disabledReason} onClick={onConfirm} className="flex-1 sm:flex-none">
          Hold &amp; pay
        </Button>
      </div>
    </div>
  </section>
);
