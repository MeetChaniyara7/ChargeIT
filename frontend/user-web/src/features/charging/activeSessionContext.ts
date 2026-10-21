import { createContext, useContext } from 'react';
import type { LiveSession } from './types';

export interface ActiveSessionState {
  /** The session that is charging right now, or null. */
  active: LiveSession | null;
  /** True until the first answer. */
  loading: boolean;
  /** Ask the API again (e.g. right after starting or stopping a session). */
  refresh: () => void;
}

export const ActiveSessionContext = createContext<ActiveSessionState>({ active: null, loading: false, refresh: () => {} });

/** The driver's running charging session, shared by the app bar pill, the Charging tab and its page. */
export const useActiveSession = (): ActiveSessionState => useContext(ActiveSessionContext);
