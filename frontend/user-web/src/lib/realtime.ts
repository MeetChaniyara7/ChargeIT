// Live "something changed" nudges from Supabase Realtime (docs/architecture.md section 11).
//
// The database sends a tiny message to the topic `station:<id>` whenever a booking, a charger or a
// charging session at that station changes. The message says WHICH station, nothing more. This file
// only listens: callers react by asking the API for fresh data. The body of a message is never used.
//
// If Realtime is not configured or drops, callers fall back to polling (see useRealtimeRefresh).

import { createClient } from '@supabase/supabase-js';
import type { RealtimeChannel, SupabaseClient } from '@supabase/supabase-js';

const url: string | undefined = import.meta.env.VITE_SUPABASE_URL;
const anonKey: string | undefined = import.meta.env.VITE_SUPABASE_ANON_KEY;

/** False when the Supabase values are missing or still the placeholders from .env.example. */
export const realtimeConfigured = Boolean(url && anonKey && !url.includes('your-supabase-project') && !anonKey.includes('your-supabase'));

export type RealtimeState = 'connecting' | 'live' | 'down';

/** If a channel has not connected within this long, it counts as down (so the banner and polling start). */
const CONNECT_TIMEOUT_MS = 8000;

interface Entry {
  channel: RealtimeChannel;
  nudges: Set<() => void>;
  states: Set<(state: RealtimeState) => void>;
  state: RealtimeState;
  timer: number | undefined;
}

let client: SupabaseClient | null = null;
const entries = new Map<string, Entry>();
const globalListeners = new Set<() => void>();

const getClient = (): SupabaseClient => {
  client ??= createClient(url as string, anonKey as string, {
    // Only Realtime is used: no sign-in through Supabase, nothing stored.
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
    realtime: { params: { eventsPerSecond: 10 } },
  });
  return client;
};

const setState = (entry: Entry, state: RealtimeState) => {
  if (entry.state === state) return;
  entry.state = state;
  entry.states.forEach((listener) => listener(state));
  globalListeners.forEach((listener) => listener());
};

function open(stationId: string): Entry {
  const channel = getClient().channel(`station:${stationId}`);
  const entry: Entry = { channel, nudges: new Set(), states: new Set(), state: 'connecting', timer: undefined };
  // Message bodies are ignored on purpose: "changed" is all we need to know.
  channel.on('broadcast', { event: 'changed' }, () => entry.nudges.forEach((nudge) => nudge()));
  channel.subscribe((status) => {
    window.clearTimeout(entry.timer);
    if (status === 'SUBSCRIBED') setState(entry, 'live');
    else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT' || status === 'CLOSED') setState(entry, 'down');
  });
  entry.timer = window.setTimeout(() => {
    if (entry.state === 'connecting') setState(entry, 'down');
  }, CONNECT_TIMEOUT_MS);
  entries.set(stationId, entry);
  return entry;
}

/**
 * Listens for changes at one station. Several listeners share one channel; the channel closes when the
 * last one leaves. `onState` is told about connecting / live / down. Returns a function that stops listening.
 */
export function subscribeToStation(stationId: string, onNudge: () => void, onState: (state: RealtimeState) => void): () => void {
  if (!realtimeConfigured) {
    onState('down');
    return () => {};
  }
  const entry = entries.get(stationId) ?? open(stationId);
  entry.nudges.add(onNudge);
  entry.states.add(onState);
  onState(entry.state);
  return () => {
    entry.nudges.delete(onNudge);
    entry.states.delete(onState);
    if (entry.nudges.size === 0 && entries.get(stationId) === entry) {
      window.clearTimeout(entry.timer);
      entries.delete(stationId);
      void getClient().removeChannel(entry.channel);
      globalListeners.forEach((listener) => listener());
    }
  };
}

// ---- "is any live connection down?", for the Reconnecting banner ----

export const subscribeToStatus = (listener: () => void): (() => void) => {
  globalListeners.add(listener);
  return () => globalListeners.delete(listener);
};

/** True while at least one open channel is down (the connection dropped and polling has taken over). */
export const anyChannelDown = (): boolean => [...entries.values()].some((entry) => entry.state === 'down');
