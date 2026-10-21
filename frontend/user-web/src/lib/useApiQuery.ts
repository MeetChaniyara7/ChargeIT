import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from './api';

interface QueryState<T> {
  /** The key the stored result belongs to. */
  key: string | null;
  data: T | undefined;
  error: string | null;
}

export interface QueryResult<T> {
  /** The latest data. While a newer request is loading this is still the previous data, so lists don't flash empty. */
  data: T | undefined;
  /** No data yet and a request is running. */
  loading: boolean;
  /** Have data from an earlier request and a newer one is running. */
  refreshing: boolean;
  /** A message when the latest request failed. */
  error: string | null;
  /** Try again from scratch: shows the loading state (for a "Try again" button). */
  retry: () => void;
  /** Ask again quietly: the current data stays on screen and is swapped when the new answer arrives (live updates, polling). */
  refresh: () => void;
}

/**
 * Fetches data whenever `key` changes (a string describing the request). Pass `null` to wait.
 * Older requests are cancelled, so a slow answer can never overwrite a newer one.
 */
export function useApiQuery<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>): QueryResult<T> {
  const [state, setState] = useState<QueryState<T>>({ key: null, data: undefined, error: null });
  const [attempt, setAttempt] = useState(0);

  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    fetcherRef.current(controller.signal).then(
      (data) => setState({ key, data, error: null }),
      (err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        const message = err instanceof ApiError || err instanceof Error ? err.message : 'Something went wrong.';
        setState((previous) => ({ key, data: previous.data, error: message }));
      },
    );
    return () => controller.abort();
  }, [key, attempt]);

  const retry = useCallback(() => {
    setState((previous) => ({ ...previous, key: null, error: null }));
    setAttempt((n) => n + 1);
  }, []);

  const refresh = useCallback(() => setAttempt((n) => n + 1), []);

  const settled = state.key === key;
  const waiting = key !== null && !settled;
  return {
    data: state.data,
    loading: waiting && state.data === undefined,
    refreshing: waiting && state.data !== undefined,
    error: settled ? state.error : null,
    retry,
    refresh,
  };
}
