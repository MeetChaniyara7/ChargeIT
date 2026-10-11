import React, { useEffect, useRef } from 'react';
import { formatDateIST, formatTimeIST, istDateKey } from '@chargespot/shared';
import { cx } from '../../components/ui';
import type { AvailabilityBlock, BlockState, ChargerAvailability, StationAvailability } from './types';

const CELL_PX = 36; // width of one 30-minute block
const LABEL_PX = 128; // width of the sticky charger-name column
const SLOT_MINUTES = 30;

// Every state differs in pattern as well as colour, so nothing relies on colour alone.
const STATE_CLASS: Record<BlockState, string> = {
  FREE: 'border border-primary/60 bg-primary/10',
  BOOKED: 'bg-field-border',
  HELD: 'border border-warning/60 bg-[repeating-linear-gradient(45deg,color-mix(in_srgb,var(--color-warning)_55%,transparent)_0_3px,transparent_3px_7px)]',
  PAST: 'bg-raised/50 opacity-50',
  OUT_OF_SERVICE: 'border border-danger/50 bg-[repeating-linear-gradient(135deg,color-mix(in_srgb,var(--color-danger)_55%,transparent)_0_2px,transparent_2px_6px)]',
};

const STATE_WORD: Record<BlockState, string> = {
  FREE: 'free',
  BOOKED: 'booked',
  HELD: 'held while someone pays',
  PAST: 'past',
  OUT_OF_SERVICE: 'out of service',
};

const LEGEND: { state: BlockState; label: string }[] = [
  { state: 'FREE', label: 'Free' },
  { state: 'BOOKED', label: 'Booked' },
  { state: 'HELD', label: 'Held' },
  { state: 'PAST', label: 'Past' },
  { state: 'OUT_OF_SERVICE', label: 'Out of service' },
];

const hourLabel = (hour: number) => (hour === 0 ? '12 AM' : hour < 12 ? `${hour} AM` : hour === 12 ? '12 PM' : `${hour - 12} PM`);

export interface BlockSelection {
  chargerId: string;
  /** First selected block's start and last selected block's end (ISO timestamps). */
  startIso: string;
  endIso: string;
}

export interface AvailabilityGridProps {
  availability: StationAvailability;
  /**
   * Phase 4 hook. When given, FREE blocks become buttons and call this when activated.
   * When absent (Phase 3), the grid is read-only.
   */
  onBlockClick?: (charger: ChargerAvailability, block: AvailabilityBlock) => void;
  /** Phase 4 hook: blocks to draw as selected. */
  selection?: BlockSelection | null;
}

const isSelected = (selection: BlockSelection | null | undefined, charger: ChargerAvailability, block: AvailabilityBlock) =>
  !!selection &&
  selection.chargerId === charger.charger_id &&
  new Date(block.start) >= new Date(selection.startIso) &&
  new Date(block.end) <= new Date(selection.endIso);

/**
 * The slot grid: one row per charger, one column per 30 minutes of the day (India time).
 * Every block's state comes from the server; nothing is worked out here.
 * The charger names stay in view while you scroll sideways, and a line marks "now" on today.
 */
export const AvailabilityGrid: React.FC<AvailabilityGridProps> = ({ availability, onBlockClick, selection }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const firstBlock = availability.chargers[0]?.blocks[0];
  const blockCount = availability.chargers[0]?.blocks.length ?? 48;

  // "Now" comes from the server's clock, and only shows when the grid is today.
  const isToday = availability.date === istDateKey(new Date(availability.now));
  const minutesIntoDay = firstBlock ? (new Date(availability.now).getTime() - new Date(firstBlock.start).getTime()) / 60000 : 0;
  const nowLeft = LABEL_PX + (minutesIntoDay / SLOT_MINUTES) * CELL_PX;

  // On today, scroll so "now" is near the left of the view; other days start at midnight.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollLeft = isToday ? Math.max(0, nowLeft - el.clientWidth / 3) : 0;
  }, [isToday, nowLeft, availability.date]);

  const dayLabel = firstBlock ? formatDateIST(firstBlock.start) : availability.date;

  return (
    <div>
      <div
        ref={scrollRef}
        tabIndex={0}
        role="region"
        aria-label={`Availability on ${dayLabel}. Scroll sideways to see the whole day.`}
        className="relative overflow-x-auto rounded-card border border-border bg-surface"
      >
        <div className="relative" style={{ width: LABEL_PX + blockCount * CELL_PX }}>
          {isToday && minutesIntoDay >= 0 && (
            <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 z-[5] w-0.5 bg-info" style={{ left: nowLeft }}>
              <span className="absolute -top-0 left-1 rounded bg-info px-1 text-[10px] font-bold text-on-primary">Now</span>
            </div>
          )}
          <table className="w-full table-fixed border-separate border-spacing-0">
            <caption className="sr-only">
              Each row is a charger and each cell a 30-minute slot on {dayLabel}, with its state: free, booked, held, past or out of service.
            </caption>
            <colgroup>
              <col style={{ width: LABEL_PX }} />
              {Array.from({ length: blockCount }, (_, i) => (
                <col key={i} style={{ width: CELL_PX }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 border-b border-r border-border bg-surface p-2 text-left text-xs font-bold text-muted">
                  Charger
                </th>
                {Array.from({ length: blockCount / 2 }, (_, hour) => (
                  <th key={hour} scope="col" colSpan={2} className="num border-b border-border px-1 py-2 text-left text-xs font-medium text-muted">
                    {hourLabel(hour)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {availability.chargers.map((charger) => (
                <tr key={charger.charger_id}>
                  <th scope="row" className="sticky left-0 z-10 border-r border-border bg-surface p-2 text-left align-middle">
                    <span className="block truncate text-sm font-bold">{charger.label}</span>
                    <span className="num block truncate text-xs font-normal text-muted">
                      {charger.power_kw ? `${charger.power_kw} kW` : 'kW unknown'}
                    </span>
                  </th>
                  {charger.blocks.map((block) => {
                    const range = `${formatTimeIST(block.start)} to ${formatTimeIST(block.end)}`;
                    const description = `${charger.label}, ${range}, ${STATE_WORD[block.state]}`;
                    const selected = isSelected(selection, charger, block);
                    const swatch = cx('h-10 rounded', STATE_CLASS[block.state], selected && 'ring-2 ring-primary ring-offset-1 ring-offset-surface');
                    const clickable = onBlockClick && block.state === 'FREE';
                    return (
                      <td key={block.start} className="p-0.5">
                        {clickable ? (
                          <button
                            type="button"
                            aria-label={description}
                            aria-pressed={selected}
                            onClick={() => onBlockClick(charger, block)}
                            className={cx('block w-full', swatch)}
                          />
                        ) : (
                          <>
                            <div className={swatch} aria-hidden="true" />
                            <span className="sr-only">{description}</span>
                          </>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted" aria-label="Legend">
        {LEGEND.map(({ state, label }) => (
          <li key={state} className="flex items-center gap-1.5">
            <span className={cx('inline-block h-4 w-6 rounded', STATE_CLASS[state])} aria-hidden="true" />
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
};
