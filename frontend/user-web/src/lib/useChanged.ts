import { useEffect, useState } from 'react';

interface Tracked {
  snapshot: ReadonlyMap<string, string> | null;
  group: string;
  changed: ReadonlySet<string>;
  /** Counts up whenever something changed, so a later clean-up only clears the flash it belongs to. */
  stamp: number;
}

const NONE: ReadonlySet<string> = new Set();

/**
 * Which entries of a snapshot changed since the previous one: used to flash blocks on the grid that
 * changed on their own (a live update). `group` names what the snapshot is about (e.g. the day shown):
 * switching group is not a change, so nothing flashes then. The flash is cleared after `holdMs`.
 *
 * `snapshot` must keep the same identity until the data really changes (build it with useMemo).
 */
export function useChanged(snapshot: ReadonlyMap<string, string> | null, group: string, holdMs = 1400): ReadonlySet<string> {
  const [tracked, setTracked] = useState<Tracked>({ snapshot, group, changed: NONE, stamp: 0 });

  // Compared while rendering (React allows updating state from the same component's render, once per change).
  if (snapshot !== tracked.snapshot) {
    const changed = new Set<string>();
    if (snapshot && tracked.snapshot && tracked.group === group) {
      for (const [key, value] of snapshot) if (tracked.snapshot.get(key) !== value) changed.add(key);
    }
    setTracked({ snapshot, group, changed, stamp: changed.size > 0 ? tracked.stamp + 1 : tracked.stamp });
  }

  const { stamp, changed } = tracked;
  useEffect(() => {
    if (changed.size === 0) return;
    const timer = window.setTimeout(() => setTracked((current) => (current.stamp === stamp ? { ...current, changed: NONE } : current)), holdMs);
    return () => window.clearTimeout(timer);
  }, [stamp, changed, holdMs]);

  return tracked.changed;
}
