import { useCallback, useState } from 'react';
import { RECENT_SEARCH_LIMIT } from './constants';

// Kept only in this browser, never sent to the API. Storage can be blocked (private
// windows, cleared site data), so every read and write is allowed to fail quietly.
const KEY = 'chargespot:recent-searches';

function load(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string').slice(0, RECENT_SEARCH_LIMIT) : [];
  } catch {
    return [];
  }
}

function save(list: string[]) {
  try {
    if (list.length) localStorage.setItem(KEY, JSON.stringify(list));
    else localStorage.removeItem(KEY);
  } catch {
    // Storage unavailable: recent searches just won't be remembered.
  }
}

/** The last few searches, newest first, without duplicates (ignoring capitals). */
export function useRecentSearches() {
  const [recent, setRecent] = useState<string[]>(load);

  const add = useCallback((text: string) => {
    const value = text.trim();
    if (!value) return;
    setRecent((previous) => {
      const next = [value, ...previous.filter((r) => r.toLowerCase() !== value.toLowerCase())].slice(0, RECENT_SEARCH_LIMIT);
      save(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    save([]);
    setRecent([]);
  }, []);

  return { recent, add, clear };
}
