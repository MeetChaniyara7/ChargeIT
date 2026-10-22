import React, { useCallback, useEffect, useState } from 'react';
import { ConnectionOverlay } from '../components/ConnectionOverlay';
import { ScreenFrame } from '../components/ScreenFrame';
import { keyStorage } from '../lib/api';
import { useKioskStatus } from '../lib/useKioskStatus';
import { useServerNow } from '../lib/useNow';
import { useWakeLock } from '../lib/useWakeLock';
import { BoardScreen } from '../screens/BoardScreen';
import { OtpScreen } from '../screens/OtpScreen';
import { SetupScreen } from '../screens/SetupScreen';
import { StartedScreen } from '../screens/StartedScreen';
import { WalkInFlow } from '../screens/WalkInFlow';

/** Used when the server does not say: after this many seconds without a touch a screen goes back to the board. */
export const IDLE_RESET_SECONDS = 30;

type View =
  | { name: 'board' }
  | { name: 'otp' }
  | { name: 'walkin' }
  | { name: 'started'; chargerLabel: string; connectorType: string; headline: string }
  | { name: 'setup' };

export const App: React.FC = () => {
  const [key, setKey] = useState<string | null>(() => keyStorage.get());
  const [view, setView] = useState<View>({ name: 'board' });

  const board = useKioskStatus(key !== null && view.name !== 'setup', key);
  const now = useServerNow(board.offsetMs);
  useWakeLock(key !== null);
  const showSetup = key === null || view.name === 'setup' || board.keyRejected;

  // The server no longer accepts this kiosk key: forget it (the setup screen then says why).
  const keyRejected = board.keyRejected;
  useEffect(() => {
    if (keyRejected) keyStorage.clear();
  }, [keyRejected]);

  const refresh = board.refresh;
  const goBoard = useCallback(() => {
    setView({ name: 'board' });
    refresh();
  }, [refresh]);

  if (showSetup) {
    return (
      <SetupScreen
        notice={keyRejected ? 'This kiosk key is not valid any more. Ask the station owner for a new one.' : null}
        onCancel={key !== null && !keyRejected ? goBoard : undefined}
        onConnected={() => {
          setKey(keyStorage.get());
          setView({ name: 'board' });
        }}
      />
    );
  }

  const status = board.status;
  return (
    <>
      <ScreenFrame stationName={status?.station_name ?? null} now={now} onSecret={() => setView({ name: 'setup' })}>
        {status === null ? (
          <p className="mt-32 text-center text-3xl font-bold text-muted" role="status">
            Loading the chargers…
          </p>
        ) : view.name === 'otp' ? (
          <OtpScreen
            idleSeconds={status.idle_reset_seconds ?? IDLE_RESET_SECONDS}
            onBack={goBoard}
            onStarted={(result) => {
              refresh();
              setView({ name: 'started', chargerLabel: result.charger_label, connectorType: result.connector_type, headline: 'Code accepted' });
            }}
          />
        ) : view.name === 'walkin' ? (
          <WalkInFlow
            status={status}
            idleSeconds={status.idle_reset_seconds ?? IDLE_RESET_SECONDS}
            refreshBoard={refresh}
            onExit={goBoard}
            onPaid={(chargerLabel, connectorType) => setView({ name: 'started', chargerLabel, connectorType, headline: 'Payment received ✓' })}
          />
        ) : view.name === 'started' ? (
          <StartedScreen chargerLabel={view.chargerLabel} connectorType={view.connectorType} headline={view.headline} onDone={goBoard} />
        ) : (
          <BoardScreen status={status} onOtp={() => setView({ name: 'otp' })} onWalkIn={() => setView({ name: 'walkin' })} />
        )}
      </ScreenFrame>
      {board.offline && <ConnectionOverlay />}
    </>
  );
};

export default App;
