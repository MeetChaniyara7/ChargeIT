import { useEffect, useRef } from 'react';

const TOUCH_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel'] as const;

/**
 * Calls `onIdle` once after `seconds` without a touch. Any touch starts the count again.
 * `active` turns it off on screens that end by themselves (the QR code with its own 3-minute timer).
 */
export function useIdleTimer(active: boolean, seconds: number, onIdle: () => void): void {
  const callback = useRef(onIdle);
  useEffect(() => {
    callback.current = onIdle;
  });

  useEffect(() => {
    if (!active) return;
    let timer = window.setTimeout(() => callback.current(), seconds * 1000);
    const restart = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback.current(), seconds * 1000);
    };
    for (const name of TOUCH_EVENTS) window.addEventListener(name, restart, { passive: true });
    return () => {
      window.clearTimeout(timer);
      for (const name of TOUCH_EVENTS) window.removeEventListener(name, restart);
    };
  }, [active, seconds]);
}
