import { useCallback, useRef } from 'react';

/** Props that call `onLongPress` after the finger stays down for `ms` (the hidden way back to the setup screen). */
export function useLongPress(onLongPress: () => void, ms = 3000) {
  const timer = useRef<number | undefined>(undefined);
  const cancel = useCallback(() => window.clearTimeout(timer.current), []);
  const start = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(onLongPress, ms);
  }, [onLongPress, ms]);
  return { onPointerDown: start, onPointerUp: cancel, onPointerLeave: cancel, onPointerCancel: cancel };
}
