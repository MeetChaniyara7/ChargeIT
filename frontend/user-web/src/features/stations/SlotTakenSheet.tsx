import React from 'react';
import { Link } from 'react-router-dom';
import { Button, buttonClasses, Money, Sheet } from '../../components/ui';
import { formatSlot } from '../bookings/format';
import type { Alternatives } from '../bookings/types';

interface SlotTakenSheetProps {
  open: boolean;
  onClose: () => void;
  alternatives: Alternatives | null;
  /** Book one of the alternatives in one tap. */
  onBook: (chargerId: string, startIso: string, blocks: number) => void;
  busy: boolean;
}

/** "Just taken. Here are alternatives": the API's suggestions, each bookable in one tap. */
export const SlotTakenSheet: React.FC<SlotTakenSheetProps> = ({ open, onClose, alternatives, onBook, busy }) => {
  const nothing =
    alternatives && alternatives.same_charger.length === 0 && alternatives.other_chargers.length === 0 && alternatives.stations.length === 0;
  return (
    <Sheet open={open} onClose={onClose} title="Just taken. Here are alternatives">
      <p className="text-sm text-muted">Someone booked those blocks a moment ago. Pick another and we will hold it for you.</p>
      {alternatives && (
        <div className="mt-4 space-y-5">
          {alternatives.same_charger.length > 0 && (
            <section aria-labelledby="alt-same">
              <h3 id="alt-same" className="text-sm font-bold">
                Same charger, other times
              </h3>
              <ul className="mt-2 space-y-2">
                {alternatives.same_charger.map((slot) => (
                  <li key={slot.start} className="flex items-center justify-between gap-3 rounded-card border border-border p-3">
                    <span className="num text-sm font-medium">{formatSlot(slot.start, slot.end)}</span>
                    <Button size="sm" disabled={busy} onClick={() => onBook(alternatives.charger_id, slot.start, alternatives.blocks)}>
                      Hold this
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {alternatives.other_chargers.length > 0 && (
            <section aria-labelledby="alt-other">
              <h3 id="alt-other" className="text-sm font-bold">
                Other chargers here, same time
              </h3>
              <ul className="mt-2 space-y-2">
                {alternatives.other_chargers.map((charger) => (
                  <li key={charger.charger_id} className="flex items-center justify-between gap-3 rounded-card border border-border p-3">
                    <span className="min-w-0 text-sm">
                      <span className="block font-medium">{charger.label}</span>
                      <span className="num block text-xs text-muted">
                        {formatSlot(charger.start, charger.end)}
                        {charger.power_kw ? ` · ${charger.power_kw} kW` : ''} · <Money value={charger.price_per_kwh} perKwh />
                      </span>
                    </span>
                    <Button size="sm" disabled={busy} onClick={() => onBook(charger.charger_id, charger.start, alternatives.blocks)}>
                      Hold this
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {alternatives.stations.length > 0 && (
            <section aria-labelledby="alt-stations">
              <h3 id="alt-stations" className="text-sm font-bold">
                Nearby stations
              </h3>
              <ul className="mt-2 space-y-2">
                {alternatives.stations.map((station) => (
                  <li key={station.station_id} className="flex items-center justify-between gap-3 rounded-card border border-border p-3">
                    <span className="min-w-0 text-sm">
                      <span className="block truncate font-medium">{station.name}</span>
                      <span className="block text-xs text-muted">{station.reason}</span>
                    </span>
                    <Link to={`/stations/${station.station_id}`} onClick={onClose} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
                      See chargers
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {nothing && <p className="text-sm text-muted">We could not find a free time nearby. Try another day or another station.</p>}
        </div>
      )}
    </Sheet>
  );
};
