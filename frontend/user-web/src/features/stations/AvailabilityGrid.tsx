import React, { useCallback, useEffect, useRef, useState } from 'react';
import { formatDateIST, formatTimeIST, istDateKey } from '@chargespot/shared';
import { cx } from '../../components/ui';
import { chooseBlock, dragBlocks, dragPreview, indexesOf } from './selection';
import type { Selection } from './selection';
import type { BlockState, ChargerAvailability, StationAvailability } from './types';

const CELL_PX = 36; // width of one 30-minute block
const LABEL_PX = 144; // width of the sticky charger-name column
const SLOT_MINUTES = 30;

// Every state differs in pattern as well as colour, so nothing relies on colour alone.
const STATE_CLASS: Record<BlockState | 'SELECTED', string> = {
  FREE: 'border border-primary/60 bg-primary/10',
  BOOKED: 'bg-field-border',
  HELD: 'border border-warning/60 bg-[repeating-linear-gradient(45deg,color-mix(in_srgb,var(--color-warning)_55%,transparent)_0_3px,transparent_3px_7px)]',
  PAST: 'bg-raised/50 opacity-50',
  OUT_OF_SERVICE: 'border border-danger/50 bg-[repeating-linear-gradient(135deg,color-mix(in_srgb,var(--color-danger)_55%,transparent)_0_2px,transparent_2px_6px)]',
  SELECTED: 'border-2 border-primary bg-primary shadow-[0_0_0_2px_color-mix(in_srgb,var(--color-primary)_35%,transparent)]',
};

const STATE_WORD: Record<BlockState, string> = {
  FREE: 'free',
  BOOKED: 'booked',
  HELD: 'held while someone pays',
  PAST: 'past',
  OUT_OF_SERVICE: 'out of service',
};

const LEGEND: { state: BlockState | 'SELECTED'; label: string }[] = [
  { state: 'FREE', label: 'Free' },
  { state: 'SELECTED', label: 'Your pick' },
  { state: 'BOOKED', label: 'Booked' },
  { state: 'HELD', label: 'Held' },
  { state: 'PAST', label: 'Past' },
  { state: 'OUT_OF_SERVICE', label: 'Out of service' },
];

const hourLabel = (hour: number) => (hour === 0 ? '12 AM' : hour < 12 ? `${hour} AM` : hour === 12 ? '12 PM' : `${hour - 12} PM`);

export type { Selection };

export interface AvailabilityGridProps {
  availability: StationAvailability;
  /** The blocks the driver has picked (one charger, 1 to 4 adjacent blocks). */
  selection?: Selection | null;
  /** Called with the new selection (or null to clear it). When absent, the grid is read-only. */
  onSelectionChange?: (selection: Selection | null) => void;
  /** Called with a short reason when a tap or drag is not allowed ("That block is already booked."). */
  onInvalid?: (message: string) => void;
  /** Extra content under a charger's name, e.g. a "Charge now" button. */
  rowAction?: (charger: ChargerAvailability) => React.ReactNode;
}

/**
 * The slot grid: one row per charger, one column per 30 minutes of the day (India time).
 * Every block's state comes from the server; nothing is worked out here except which blocks the
 * driver has picked.
 *
 * Picking: tap a start block and an end block, or drag with a mouse. Keyboard: arrow keys move,
 * Enter or Space picks. 1 to 4 adjacent free blocks on one charger; anything else says why.
 * The charger names stay in view while you scroll sideways, and a line marks "now" on today.
 */
export const AvailabilityGrid: React.FC<AvailabilityGridProps> = ({ availability, selection = null, onSelectionChange, onInvalid, rowAction }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const cellRefs = useRef(new Map<string, HTMLButtonElement>());
  const firstBlock = availability.chargers[0]?.blocks[0];
  const blockCount = availability.chargers[0]?.blocks.length ?? 48;
  const interactive = !!onSelectionChange;

  // "Now" comes from the server's clock, and only shows when the grid is today.
  const isToday = availability.date === istDateKey(new Date(availability.now));
  const minutesIntoDay = firstBlock ? (new Date(availability.now).getTime() - new Date(firstBlock.start).getTime()) / 60000 : 0;
  const nowLeft = LABEL_PX + (minutesIntoDay / SLOT_MINUTES) * CELL_PX;
  const nowIndex = Math.max(0, Math.min(blockCount - 1, Math.floor(minutesIntoDay / SLOT_MINUTES)));

  // On today, scroll so "now" is near the left of the view; other days start at midnight.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollLeft = isToday ? Math.max(0, nowLeft - el.clientWidth / 3) : 0;
  }, [isToday, nowLeft, availability.date]);

  // ---- keyboard: one cell is in the tab order; arrows move between cells ----
  const [focusCell, setFocusCell] = useState<[number, number]>([0, nowIndex]);
  const moveFocus = useCallback(
    (row: number, column: number) => {
      const r = Math.max(0, Math.min(availability.chargers.length - 1, row));
      const c = Math.max(0, Math.min(blockCount - 1, column));
      setFocusCell([r, c]);
      cellRefs.current.get(`${r}:${c}`)?.focus();
      cellRefs.current.get(`${r}:${c}`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    },
    [availability.chargers.length, blockCount],
  );

  // ---- mouse drag ----
  const [drag, setDrag] = useState<{ row: number; from: number; to: number } | null>(null);
  const dragRef = useRef(drag);
  const justDragged = useRef(false);
  useEffect(() => {
    dragRef.current = drag;
  });

  useEffect(() => {
    if (!drag || !onSelectionChange) return;
    const finish = () => {
      const current = dragRef.current;
      setDrag(null);
      if (!current || current.from === current.to) return; // a plain click is handled by onClick
      justDragged.current = true; // swallow the click that follows the drag
      window.setTimeout(() => {
        justDragged.current = false;
      }, 0);
      const charger = availability.chargers[current.row];
      const result = dragBlocks(charger, current.from, current.to);
      if (result.ok) onSelectionChange(result.selection);
      else onInvalid?.(result.message);
    };
    const cancel = () => setDrag(null);
    window.addEventListener('pointerup', finish, { once: true });
    window.addEventListener('pointercancel', cancel, { once: true });
    return () => {
      window.removeEventListener('pointerup', finish);
      window.removeEventListener('pointercancel', cancel);
    };
  }, [drag, availability.chargers, onSelectionChange, onInvalid]);

  const activate = (row: number, column: number) => {
    if (!onSelectionChange || justDragged.current) return;
    const result = chooseBlock(selection, availability.chargers[row], column);
    if (result.ok) onSelectionChange(result.selection);
    else onInvalid?.(result.message);
  };

  const onKeyDown = (event: React.KeyboardEvent, row: number, column: number) => {
    const moves: Record<string, [number, number]> = {
      ArrowRight: [row, column + 1],
      ArrowLeft: [row, column - 1],
      ArrowDown: [row + 1, column],
      ArrowUp: [row - 1, column],
      Home: [row, 0],
      End: [row, blockCount - 1],
    };
    const target = moves[event.key];
    if (target) {
      event.preventDefault();
      moveFocus(target[0], target[1]);
    } else if (event.key === 'Escape' && selection) {
      onSelectionChange?.(null);
    }
  };

  const dayLabel = firstBlock ? formatDateIST(firstBlock.start) : availability.date;

  return (
    <div>
      <div
        ref={scrollRef}
        className="relative overflow-x-auto rounded-card border border-border bg-surface"
        role="region"
        aria-label={`Availability on ${dayLabel}. Scroll sideways to see the whole day.`}
      >
        <div className="relative select-none" style={{ width: LABEL_PX + blockCount * CELL_PX }}>
          {isToday && minutesIntoDay >= 0 && (
            <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 z-[5] w-0.5 bg-info" style={{ left: nowLeft }}>
              <span className="absolute -top-0 left-1 rounded bg-info px-1 text-[10px] font-bold text-on-primary">Now</span>
            </div>
          )}
          <table role={interactive ? 'grid' : 'table'} className="w-full table-fixed border-separate border-spacing-0">
            <caption className="sr-only">
              {interactive
                ? `Each row is a charger and each cell a 30-minute slot on ${dayLabel}. Use the arrow keys to move and Enter or Space to pick a start and an end. You can pick up to 4 blocks.`
                : `Each row is a charger and each cell a 30-minute slot on ${dayLabel}, with its state.`}
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
              {availability.chargers.map((charger, row) => {
                const picked = indexesOf(selection, charger);
                const preview = drag && drag.row === row ? dragPreview(charger, drag.from, drag.to) : null;
                return (
                  <tr key={charger.charger_id}>
                    <th scope="row" className="sticky left-0 z-10 border-r border-border bg-surface p-2 text-left align-middle">
                      <span className="block truncate text-sm font-bold">{charger.label}</span>
                      <span className="num block truncate text-xs font-normal text-muted">
                        {charger.power_kw ? `${charger.power_kw} kW` : 'kW unknown'}
                      </span>
                      {rowAction?.(charger)}
                    </th>
                    {charger.blocks.map((block, column) => {
                      const range = `${formatTimeIST(block.start)} to ${formatTimeIST(block.end)}`;
                      const chosen = (picked && column >= picked[0] && column <= picked[1]) || (preview && column >= preview[0] && column <= preview[1]);
                      const description = `${charger.label}, ${range}, ${chosen ? 'your pick' : STATE_WORD[block.state]}`;
                      const swatch = cx('h-10 w-full rounded', STATE_CLASS[chosen ? 'SELECTED' : block.state]);
                      return (
                        <td key={block.start} role={interactive ? 'gridcell' : undefined} aria-selected={interactive ? !!chosen : undefined} className="p-0.5">
                          {interactive ? (
                            <button
                              type="button"
                              ref={(el) => {
                                const key = `${row}:${column}`;
                                if (el) cellRefs.current.set(key, el);
                                else cellRefs.current.delete(key);
                              }}
                              tabIndex={focusCell[0] === row && focusCell[1] === column ? 0 : -1}
                              aria-label={description}
                              aria-disabled={block.state !== 'FREE' || undefined}
                              onFocus={() => setFocusCell([row, column])}
                              onKeyDown={(e) => onKeyDown(e, row, column)}
                              onClick={() => activate(row, column)}
                              onPointerDown={(e) => {
                                // Dragging is for a mouse; on a touch screen a drag scrolls the grid.
                                if (e.pointerType === 'mouse' && e.button === 0 && block.state === 'FREE') setDrag({ row, from: column, to: column });
                              }}
                              onPointerEnter={() => setDrag((d) => (d && d.row === row ? { ...d, to: column } : d))}
                              className={cx('block rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-info', swatch)}
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
                );
              })}
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
