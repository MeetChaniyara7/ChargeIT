import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent, ReactNode } from 'react';
import { cx } from './cx';

export type Snap = 'peek' | 'half' | 'full';
const ORDER: Snap[] = ['peek', 'half', 'full'];

/** Dragging shorter than this (in px) counts as a tap. */
const TAP_DISTANCE = 6;
/** How far ahead (ms) a fast flick is projected, so a quick swipe goes to the next snap point. */
const FLICK_PROJECTION_MS = 150;

export interface SnapSheetProps {
  snap: Snap;
  onSnapChange: (snap: Snap) => void;
  /** Names the panel for screen readers, e.g. "Nearby stations". */
  label: string;
  /** Shown next to the drag handle: a title or a count. Visible even when the sheet is at its lowest. */
  summary?: ReactNode;
  /** How much of the sheet shows at its lowest position (handle, summary and about one card). */
  peekHeight?: number;
  children: ReactNode;
}

/**
 * A panel that slides up over its parent (a map) and stays at one of three heights:
 * peek (a glimpse), half, or full.
 *
 * Drag the handle area with a finger or a mouse, tap it to move to the next height, or use the
 * keyboard on the handle button: Enter/Space = next height, Up/Down = one height up/down, Esc = lowest.
 * The parent must be `position: relative` and give the sheet room (it uses the parent's height).
 */
export function SnapSheet({ snap, onSnapChange, label, summary, peekHeight = 232, children }: SnapSheetProps) {
  const sheetRef = useRef<HTMLElement>(null);
  const [containerHeight, setContainerHeight] = useState(0);
  const [drag, setDrag] = useState<{ startY: number; startOffset: number; offset: number } | null>(null);
  const lastMove = useRef({ y: 0, time: 0, velocity: 0 });

  // The sheet is as tall as 92% of its parent. Keep that in step with the parent's size.
  useEffect(() => {
    const parent = sheetRef.current?.parentElement;
    if (!parent) return;
    const measure = () => setContainerHeight(parent.clientHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(parent);
    return () => observer.disconnect();
  }, []);

  const sheetHeight = Math.round(containerHeight * 0.92);
  // How far the sheet is pushed down for each snap point (0 = fully open).
  const offsets: Record<Snap, number> = {
    peek: Math.max(0, sheetHeight - Math.min(peekHeight, sheetHeight)),
    half: Math.max(0, sheetHeight - Math.round(containerHeight * 0.5)),
    full: 0,
  };
  const offset = drag ? drag.offset : offsets[snap];

  const nearestSnap = (target: number): Snap =>
    ORDER.reduce((best, s) => (Math.abs(offsets[s] - target) < Math.abs(offsets[best] - target) ? s : best), snap);
  const next = (from: Snap, step: 1 | -1): Snap => ORDER[Math.min(ORDER.length - 1, Math.max(0, ORDER.indexOf(from) + step))];

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    lastMove.current = { y: e.clientY, time: e.timeStamp, velocity: 0 };
    setDrag({ startY: e.clientY, startOffset: offsets[snap], offset: offsets[snap] });
  };

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    const dt = Math.max(1, e.timeStamp - lastMove.current.time);
    lastMove.current = { y: e.clientY, time: e.timeStamp, velocity: (e.clientY - lastMove.current.y) / dt };
    const raw = drag.startOffset + (e.clientY - drag.startY);
    setDrag({ ...drag, offset: Math.min(offsets.peek, Math.max(0, raw)) });
  };

  const onPointerUp = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    const moved = Math.abs(e.clientY - drag.startY);
    setDrag(null);
    if (moved < TAP_DISTANCE) {
      onSnapChange(snap === 'full' ? 'peek' : next(snap, 1)); // a tap steps up, and wraps back down from the top
      return;
    }
    onSnapChange(nearestSnap(drag.offset + lastMove.current.velocity * FLICK_PROJECTION_MS));
  };

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'ArrowUp') onSnapChange(next(snap, 1));
    else if (e.key === 'ArrowDown') onSnapChange(next(snap, -1));
    else if (e.key === 'Escape') onSnapChange('peek');
    else return;
    e.preventDefault();
  };

  const nextLabel = snap === 'full' ? 'Collapse the list' : 'Expand the list';

  return (
    <section
      ref={sheetRef}
      role="region"
      aria-label={label}
      style={{ height: sheetHeight || undefined, transform: `translateY(${offset}px)` }}
      className={cx(
        'absolute inset-x-0 bottom-0 z-20 flex flex-col rounded-t-sheet border border-b-0 border-border bg-surface shadow-e3',
        !drag && 'transition-transform duration-[250ms] ease-out',
        !sheetHeight && 'invisible',
      )}
    >
      <div
        className="touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => setDrag(null)}
      >
        <button
          type="button"
          aria-expanded={snap !== 'peek'}
          aria-label={`${nextLabel}. Drag, or use the up and down arrow keys.`}
          onKeyDown={onKeyDown}
          onClick={(e) => {
            // Keyboard activation only: pointer taps are handled in onPointerUp.
            if (e.detail === 0) onSnapChange(snap === 'full' ? 'peek' : next(snap, 1));
          }}
          className="flex min-h-11 w-full cursor-grab flex-col items-center justify-center gap-2 pt-2 active:cursor-grabbing"
        >
          <span className="h-1.5 w-10 rounded-full bg-field-border" aria-hidden="true" />
        </button>
        {summary && <div className="px-4 pb-2">{summary}</div>}
      </div>
      <div className={cx('min-h-0 flex-1 px-4 pb-4', snap === 'peek' && !drag ? 'overflow-hidden' : 'overflow-y-auto')}>{children}</div>
    </section>
  );
}
