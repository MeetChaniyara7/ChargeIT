import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Pencil, Plus, Power, PowerOff } from 'lucide-react';
import { CONNECTOR_LABELS, CONNECTOR_TYPES } from '@chargespot/shared';
import { Button, Card, ConfirmDialog, DataTable, Field, Money, Select, Sheet, TextInput, useToast } from '../../components/ui';
import type { Column } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { ChargerStatusBadge, PageHeader, QueryState, SourceBadge } from './shared';
import { OutOfServiceDialog } from './OutOfServiceDialog';
import { optionalNumber, validateCharger, validateStation } from './validation';
import type { ChargerValues, Errors, StationValues } from './validation';
import type { AdminCharger, AdminStation, Operator } from './types';

const BLANK_STATION: StationValues = { name: '', address: '', city: '', latitude: '', longitude: '', operatorId: '', openingHours: '' };

function valuesOf(s: AdminStation): StationValues {
  return {
    name: s.name, address: s.address, city: s.city ?? '', latitude: String(s.latitude), longitude: String(s.longitude),
    operatorId: s.operator_id ?? '', openingHours: s.opening_hours ?? '',
  };
}

// ---------------------------------------------------------------- the charger form

const ChargerSheet: React.FC<{ stationId: string; charger: AdminCharger | null; open: boolean; onClose: () => void; onSaved: () => void }> = ({
  stationId, charger, open, onClose, onSaved,
}) => {
  const toast = useToast();
  const blank: ChargerValues = { label: '', connectorType: 'CCS2', currentType: '', powerKw: '', pricePerKwh: '' };
  const [values, setValues] = useState<ChargerValues>(blank);
  const [errors, setErrors] = useState<Errors<ChargerValues>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Each time the sheet opens it starts from the charger being edited, or a blank form.
  useEffect(() => {
    if (!open) return;
    setValues(
      charger
        ? { label: charger.label, connectorType: charger.connector_type, currentType: charger.current_type ?? '', powerKw: charger.power_kw?.toString() ?? '', pricePerKwh: charger.price_per_kwh?.toString() ?? '' }
        : blank,
    );
    setErrors({});
    setProblem(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, charger]);

  const set = (name: keyof ChargerValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setValues((v) => ({ ...v, [name]: e.target.value }));

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    const found = validateCharger(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    setProblem(null);
    const body = {
      label: values.label.trim(), connector_type: values.connectorType, current_type: values.currentType || null,
      power_kw: optionalNumber(values.powerKw), price_per_kwh: optionalNumber(values.pricePerKwh),
    };
    try {
      if (charger) await apiFetch(`/api/admin/chargers/${charger.charger_id}`, { method: 'PATCH', body });
      else await apiFetch(`/api/admin/stations/${stationId}/chargers`, { method: 'POST', body });
      toast.success(charger ? 'Charger saved' : 'Charger added');
      onSaved();
      onClose();
    } catch (error) {
      setProblem(error instanceof Error ? error.message : 'Could not save the charger.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title={charger ? `Edit charger ${charger.label}` : 'Add a charger'}>
      <form onSubmit={save} className="space-y-4" noValidate>
        <Field label="Label" error={errors.label} hint="Unique at this station, for example CCS2-1">{(p) => <TextInput value={values.label} onChange={set('label')} {...p} />}</Field>
        <Field label="Plug type" error={errors.connectorType}>
          {(p) => (
            <Select value={values.connectorType} onChange={set('connectorType')} {...p}>
              {CONNECTOR_TYPES.map((c) => (
                <option key={c} value={c}>{CONNECTOR_LABELS[c]}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Current">
          {(p) => (
            <Select value={values.currentType} onChange={set('currentType')} {...p}>
              <option value="">Unknown</option>
              <option value="AC">AC</option>
              <option value="DC">DC</option>
            </Select>
          )}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Power (kW)" error={errors.powerKw} hint="Empty = unknown">{(p) => <TextInput inputMode="decimal" value={values.powerKw} onChange={set('powerKw')} {...p} />}</Field>
          <Field label="Price (₹ per kWh)" error={errors.pricePerKwh} hint="Empty = unknown">{(p) => <TextInput inputMode="decimal" value={values.pricePerKwh} onChange={set('pricePerKwh')} {...p} />}</Field>
        </div>
        {problem && <p role="alert" className="text-sm font-medium text-danger-soft">{problem}</p>}
        <p className="text-xs text-muted">Values you enter here count as real: the Approximate tag goes away.</p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" loading={busy}>{charger ? 'Save charger' : 'Add charger'}</Button>
        </div>
      </form>
    </Sheet>
  );
};

// ---------------------------------------------------------------- the page

export const StationEditPage: React.FC = () => {
  const { stationId } = useParams();
  const isNew = stationId === 'new';
  const navigate = useNavigate();
  const toast = useToast();
  const key = isNew ? null : `/api/admin/stations/${stationId}`;
  const query = useApiQuery(key, (signal) => apiFetch<AdminStation>(key as string, { signal }));
  const operators = useApiQuery('/api/admin/operators', (signal) => apiFetch<Operator[]>('/api/admin/operators', { signal }));
  const station = query.data;

  const [values, setValues] = useState<StationValues>(BLANK_STATION);
  const [active, setActive] = useState(true);
  const [errors, setErrors] = useState<Errors<StationValues>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadedFor, setLoadedFor] = useState<AdminStation | undefined>(undefined);
  const [chargerSheet, setChargerSheet] = useState<{ open: boolean; charger: AdminCharger | null }>({ open: false, charger: null });
  const [oosCharger, setOosCharger] = useState<AdminCharger | null>(null);
  const [deactivating, setDeactivating] = useState<{ count: number } | null>(null);

  // Fill the form when the station arrives (and again after a save).
  if (station && station !== loadedFor) {
    setLoadedFor(station);
    setValues(valuesOf(station));
    setActive(station.is_active);
  }

  const set = (name: keyof StationValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setValues((v) => ({ ...v, [name]: e.target.value }));

  const save = async (cancelBookings = false) => {
    const found = validateStation(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    setProblem(null);
    const common = {
      name: values.name.trim(), address: values.address.trim(), city: values.city.trim() || null,
      latitude: Number(values.latitude), longitude: Number(values.longitude), operator_id: values.operatorId || null,
    };
    try {
      if (isNew) {
        const created = await apiFetch<{ station_id: string }>('/api/stations', { method: 'POST', body: common });
        toast.success('Station created. Now add its chargers.');
        navigate(`/admin/stations/${created.station_id}`, { replace: true });
        return;
      }
      await apiFetch(`/api/admin/stations/${stationId}`, {
        method: 'PATCH',
        body: { ...common, opening_hours: values.openingHours.trim() || null, is_active: active, cancel_bookings: cancelBookings },
      });
      setDeactivating(null);
      toast.success('Station saved');
      query.refresh();
    } catch (error) {
      if (error instanceof ApiError && error.code === 'HAS_FUTURE_BOOKINGS') {
        setDeactivating({ count: Number(error.details?.count ?? 0) });
      } else {
        setProblem(error instanceof Error ? error.message : 'Could not save the station.');
      }
    } finally {
      setBusy(false);
    }
  };

  const chargerColumns: Column<AdminCharger>[] = [
    { id: 'label', header: 'Label', cell: (c) => <span className="font-bold">{c.label}</span> },
    { id: 'plug', header: 'Plug', cell: (c) => `${CONNECTOR_LABELS[c.connector_type as keyof typeof CONNECTOR_LABELS] ?? c.connector_type}${c.current_type ? ` · ${c.current_type}` : ''}` },
    { id: 'power', header: 'Power', align: 'right', cell: (c) => (c.power_kw != null ? <span className="num">{c.power_kw} kW</span> : <span className="text-muted">unknown</span>) },
    { id: 'price', header: 'Price', align: 'right', cell: (c) => <Money value={c.price_per_kwh} perKwh /> },
    { id: 'status', header: 'Status', cell: (c) => <ChargerStatusBadge status={c.status} /> },
    { id: 'source', header: 'Data', cell: (c) => <SourceBadge source={c.data_source} /> },
    {
      id: 'actions', header: 'Actions', align: 'right',
      cell: (c) => (
        <div className="flex justify-end gap-1">
          <Button size="md" variant="ghost" icon={<Pencil className="size-4" aria-hidden="true" />} onClick={() => setChargerSheet({ open: true, charger: c })} aria-label={`Edit charger ${c.label}`}>
            Edit
          </Button>
          {c.status === 'OUT_OF_SERVICE' ? (
            <Button size="md" variant="secondary" icon={<Power className="size-4" aria-hidden="true" />} onClick={() => restore(c)} aria-label={`Put charger ${c.label} back in service`}>
              Restore
            </Button>
          ) : (
            <Button size="md" variant="ghost" icon={<PowerOff className="size-4" aria-hidden="true" />} onClick={() => setOosCharger(c)} aria-label={`Set charger ${c.label} out of service`}>
              Out of service
            </Button>
          )}
        </div>
      ),
    },
  ];

  const restore = async (c: AdminCharger) => {
    try {
      await apiFetch(`/api/admin/chargers/${c.charger_id}/restore`, { method: 'POST' });
      toast.success(`Charger ${c.label} is back in service`);
      query.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not restore the charger.');
    }
  };

  return (
    <>
      <Link to="/admin/stations" className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-info">
        <ArrowLeft className="size-4" aria-hidden="true" />
        Stations
      </Link>
      <PageHeader title={isNew ? 'New station' : (station?.name ?? 'Station')} subtitle={station ? undefined : isNew ? 'Added by hand: marked as a manual record.' : undefined} />
      <QueryState loading={query.loading} error={query.error} hasData={isNew || !!station} retry={query.retry}>
        <Card className="p-4">
          <form onSubmit={(e) => { e.preventDefault(); void save(); }} className="grid gap-4 sm:grid-cols-2" noValidate>
            <Field label="Name" error={errors.name} className="sm:col-span-2">{(p) => <TextInput value={values.name} onChange={set('name')} {...p} />}</Field>
            <Field label="Address" error={errors.address} className="sm:col-span-2">{(p) => <TextInput value={values.address} onChange={set('address')} {...p} />}</Field>
            <Field label="City" error={errors.city}>{(p) => <TextInput value={values.city} onChange={set('city')} {...p} />}</Field>
            <Field label="Operator">
              {(p) => (
                <Select value={values.operatorId} onChange={set('operatorId')} {...p}>
                  <option value="">None</option>
                  {(operators.data ?? []).map((o) => (
                    <option key={o.operator_id} value={o.operator_id}>{o.name}</option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Latitude" error={errors.latitude}>{(p) => <TextInput inputMode="decimal" value={values.latitude} onChange={set('latitude')} {...p} />}</Field>
            <Field label="Longitude" error={errors.longitude}>{(p) => <TextInput inputMode="decimal" value={values.longitude} onChange={set('longitude')} {...p} />}</Field>
            {!isNew && (
              <>
                <Field label="Opening hours" error={errors.openingHours} hint="OpenStreetMap style, for example Mo-Su 06:00-22:00. Empty = unknown." className="sm:col-span-2">
                  {(p) => <TextInput value={values.openingHours} onChange={set('openingHours')} {...p} />}
                </Field>
                <label className="flex min-h-11 items-center gap-3 text-sm sm:col-span-2">
                  <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="size-5 accent-primary" />
                  <span>
                    <span className="font-medium">Active</span>
                    <span className="block text-xs text-muted">Inactive stations disappear from the map. Turning one off with future bookings asks what to do with them.</span>
                  </span>
                </label>
              </>
            )}
            {station && (
              <p className="flex items-center gap-2 text-sm text-muted sm:col-span-2">
                Data source: <SourceBadge source={station.data_source} />
              </p>
            )}
            {problem && <p role="alert" className="text-sm font-medium text-danger-soft sm:col-span-2">{problem}</p>}
            <div className="flex justify-end gap-2 sm:col-span-2">
              <Button type="submit" loading={busy}>{isNew ? 'Create station' : 'Save station'}</Button>
            </div>
          </form>
        </Card>

        {station && (
          <section aria-labelledby="chargers-heading" className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 id="chargers-heading" className="text-xl font-bold">Chargers</h2>
              <Button variant="secondary" icon={<Plus className="size-4" aria-hidden="true" />} onClick={() => setChargerSheet({ open: true, charger: null })}>
                Add charger
              </Button>
            </div>
            <DataTable
              caption={`Chargers at ${station.name}`}
              columns={chargerColumns}
              rows={station.chargers}
              rowKey={(c) => c.charger_id}
              empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">No chargers yet. Add the first one.</p>}
            />
          </section>
        )}
      </QueryState>

      {station && (
        <>
          <ChargerSheet
            stationId={station.station_id}
            charger={chargerSheet.charger}
            open={chargerSheet.open}
            onClose={() => setChargerSheet((s) => ({ ...s, open: false }))}
            onSaved={query.refresh}
          />
          <OutOfServiceDialog charger={oosCharger} onClose={() => setOosCharger(null)} onDone={query.refresh} />
          <ConfirmDialog
            open={deactivating !== null}
            title="This station has future bookings"
            confirmLabel="Cancel them with full refund and save"
            danger
            busy={busy}
            onClose={() => setDeactivating(null)}
            onConfirm={() => void save(true)}
          >
            <p>
              Taking <strong>{station.name}</strong> off the map would break <strong>{deactivating?.count} booking{deactivating?.count === 1 ? '' : 's'}</strong>.
              You can cancel {deactivating?.count === 1 ? 'it' : 'them'} now: each driver gets a notice and everything they paid is refunded in full.
            </p>
            <p className="text-muted">Or close this and leave the station active.</p>
          </ConfirmDialog>
        </>
      )}
    </>
  );
};
