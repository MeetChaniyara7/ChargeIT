import React from 'react';
import { Button, Sheet } from '../../components/ui';

interface ChargeNowSheetProps {
  open: boolean;
  onClose: () => void;
  stationName: string;
  chargerLabel: string;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
}

/** Confirms an instant booking ("Charge now"): no fee, starts immediately. */
export const ChargeNowSheet: React.FC<ChargeNowSheetProps> = ({ open, onClose, stationName, chargerLabel, busy, error, onConfirm }) => (
  <Sheet
    open={open}
    onClose={onClose}
    title="Charge now"
    footer={
      <>
        <Button variant="secondary" onClick={onClose} disabled={busy}>
          Not now
        </Button>
        <Button onClick={onConfirm} loading={busy}>
          Start with this charger
        </Button>
      </>
    }
  >
    <p className="text-base">
      <span className="font-bold">{chargerLabel}</span> at {stationName}
    </p>
    <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
      <li>
        <span className="font-medium text-fg">No booking fee.</span> You pay for the energy you use, after charging.
      </li>
      <li>Starts now and lasts up to 1 hour, or until the next booking on this charger.</li>
      <li>You will get a code to type on the screen at the station. It is shown once.</li>
    </ul>
    {error && (
      <p role="alert" className="mt-3 text-sm font-medium text-danger-soft">
        {error}
      </p>
    )}
  </Sheet>
);
