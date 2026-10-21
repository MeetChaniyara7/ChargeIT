import { useEffect, useRef, useState } from 'react';

const prefersReducedMotion = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * A number that glides to its new value instead of jumping (the battery %, kWh and cost on the live
 * charging page). It eases out over `durationMs`. With "reduce motion" on, it just snaps.
 */
export function useAnimatedNumber(target: number, durationMs = 1200): number {
  const [value, setValue] = useState(target);
  const current = useRef(target);

  useEffect(() => {
    const from = current.current;
    if (from === target) return;
    const begin = performance.now();
    const instant = prefersReducedMotion();
    let frame = 0;
    const tick = (now: number) => {
      const t = instant ? 1 : Math.min(1, (now - begin) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      current.current = from + (target - from) * eased;
      setValue(current.current);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);

  return value;
}
