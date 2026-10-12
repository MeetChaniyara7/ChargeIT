import React, { useState } from 'react';
import { CONNECTOR_LABELS, CONNECTOR_TYPES } from '@chargespot/shared';
import type { ConnectorType } from '@chargespot/shared';
import { Button, ConnectorIcon, cx, Field, Sheet, TextInput } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import type { VehicleIn, VehicleOut } from '../bookings/types';

interface VehicleSheetProps {
  open: boolean;
  /** The vehicle being edited, or null to add a new one. */
  vehicle: VehicleOut | null;
  /** True when this is the first vehicle (it becomes the default automatically). */
  isFirst: boolean;
  onClose: () => void;
  onSaved: () => void;
}

interface Errors {
  nickname?: string;
  connector?: string;
  battery?: string;
  general?: string;
}

/** Add or edit a vehicle. The whole form is checked here for quick feedback; the API checks it again. */
export const VehicleSheet: React.FC<VehicleSheetProps> = ({ open, vehicle, isFirst, onClose, onSaved }) => {
  // The form starts from the vehicle each time the sheet opens (the parent remounts it with a key).
  const [nickname, setNickname] = useState(vehicle?.nickname ?? '');
  const [connector, setConnector] = useState<ConnectorType | null>((vehicle?.connector_type as ConnectorType | undefined) ?? null);
  const [battery, setBattery] = useState(vehicle ? String(vehicle.battery_kwh) : '');
  const [makeDefault, setMakeDefault] = useState(vehicle?.is_default ?? false);
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const next: Errors = {};
    const name = nickname.trim();
    const kwh = Number(battery.replace(',', '.'));
    if (!name) next.nickname = 'Give your vehicle a name, e.g. "Nexon EV".';
    else if (name.length > 40) next.nickname = 'Keep the name to 40 characters.';
    if (!connector) next.connector = 'Pick the plug your vehicle uses.';
    if (!battery.trim() || !Number.isFinite(kwh)) next.battery = 'Enter the battery size in kWh, e.g. 40.5.';
    else if (kwh <= 0 || kwh > 250) next.battery = 'Battery size must be between 0 and 250 kWh.';
    setErrors(next);
    if (Object.keys(next).length > 0 || !connector) return;

    setBusy(true);
    const body: VehicleIn = { nickname: name, connector_type: connector, battery_kwh: kwh, is_default: makeDefault || isFirst };
    try {
      if (vehicle) await apiFetch(`/api/me/vehicles/${vehicle.vehicle_id}`, { method: 'PATCH', body });
      else await apiFetch('/api/me/vehicles', { method: 'POST', body });
      onSaved();
      onClose();
    } catch (error) {
      setErrors({ general: error instanceof ApiError ? error.message : 'Could not save. Please try again.' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={vehicle ? 'Edit vehicle' : 'Add a vehicle'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="vehicle-form" loading={busy}>
            {vehicle ? 'Save changes' : 'Add vehicle'}
          </Button>
        </>
      }
    >
      <form id="vehicle-form" onSubmit={(e) => void submit(e)} noValidate className="space-y-4">
        <Field label="Name" error={errors.nickname}>
          {(control) => <TextInput {...control} value={nickname} maxLength={40} autoComplete="off" onChange={(e) => setNickname(e.target.value)} />}
        </Field>

        <fieldset aria-describedby={errors.connector ? 'connector-error' : undefined}>
          <legend className="mb-1.5 text-sm font-medium">Plug type</legend>
          <div role="radiogroup" aria-label="Plug type" className="grid grid-cols-2 gap-2">
            {CONNECTOR_TYPES.map((type) => {
              const selected = connector === type;
              return (
                <button
                  key={type}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setConnector(type)}
                  className={cx(
                    'flex min-h-11 items-center gap-2 rounded-control border px-3 text-left text-sm transition-colors',
                    selected ? 'border-primary bg-primary/15 font-bold text-primary' : 'border-field-border bg-surface hover:bg-raised',
                  )}
                >
                  <ConnectorIcon type={type} />
                  <span className="sr-only">{CONNECTOR_LABELS[type]}</span>
                </button>
              );
            })}
          </div>
          {errors.connector && (
            <p id="connector-error" role="alert" className="mt-1.5 text-xs font-medium text-danger">
              {errors.connector}
            </p>
          )}
        </fieldset>

        <Field label="Battery size (kWh)" hint="Usable capacity, as in your car's manual. It limits the cost estimate." error={errors.battery}>
          {(control) => <TextInput {...control} value={battery} inputMode="decimal" autoComplete="off" onChange={(e) => setBattery(e.target.value)} />}
        </Field>

        {!isFirst && (
          <label className="flex min-h-11 items-center gap-3 text-sm">
            <input type="checkbox" checked={makeDefault} disabled={vehicle?.is_default} onChange={(e) => setMakeDefault(e.target.checked)} className="size-5 accent-primary" />
            Use this as my default vehicle
          </label>
        )}

        {errors.general && (
          <p role="alert" className="text-sm font-medium text-danger-soft">
            {errors.general}
          </p>
        )}
      </form>
    </Sheet>
  );
};
