import { Delete } from 'lucide-react';
import type { PadKey } from '../lib/otp';
import { cx } from './cx';

const ROWS: PadKey[][] = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['clear', '0', 'delete'],
];

/** The on-screen number pad: keys are 80 px tall on the small tablet and 100 px on the large one, above the 64 px touch minimum. */
export function Keypad({ onKey, disabled = false }: { onKey: (key: PadKey) => void; disabled?: boolean }) {
  return (
    <div className="grid shrink-0 grid-cols-3 gap-3" role="group" aria-label="Number pad">
      {ROWS.flat().map((key) => {
        const isDigit = key.length === 1;
        return (
          <button
            key={key}
            type="button"
            disabled={disabled}
            onClick={() => onKey(key)}
            aria-label={key === 'delete' ? 'Delete last digit' : key === 'clear' ? 'Clear all digits' : key}
            className={cx(
              'flex h-16 w-24 items-center justify-center rounded-card border-2 border-field-border bg-raised min-[1200px]:h-20 min-[1200px]:w-28',
              'text-3xl font-extrabold transition-colors duration-150 active:bg-border disabled:opacity-40',
              !isDigit && 'text-xl text-muted',
            )}
          >
            {key === 'delete' ? <Delete className="size-8" aria-hidden="true" /> : key === 'clear' ? 'Clear' : key}
          </button>
        );
      })}
    </div>
  );
}
