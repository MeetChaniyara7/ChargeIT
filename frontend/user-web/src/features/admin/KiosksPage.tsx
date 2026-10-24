import React, { useState } from 'react';
import { AlertTriangle, Check, Copy, KeyRound, Pencil, Plus, RefreshCw, ShieldOff } from 'lucide-react';
import { Badge, Button, ConfirmDialog, DataTable, DateTime, Field, Select, Sheet, TextInput, useToast } from '../../components/ui';
import type { Column } from '../../components/ui';
import { IconButton } from '../../components/ui/Button';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { PageHeader, QueryState } from './shared';
import type { DeviceCreated, DeviceRow, StationRows } from './types';

/** The new key, shown once with a copy button. Closing the dialog is the last time it exists in plain form. */
const KeyDialog: React.FC<{ created: DeviceCreated | null; onClose: () => void }> = ({ created, onClose }) => {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const copy = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.key);
      setCopied(true);
      setCopyFailed(false);
    } catch {
      setCopyFailed(true); // clipboard blocked: the key is selectable below
    }
  };
  return (
    <Sheet
      open={created !== null}
      onClose={() => {
        setCopied(false);
        setCopyFailed(false);
        onClose();
      }}
      title="Kiosk key created"
      footer={<div className="flex justify-end"><Button onClick={onClose}>I have saved the key</Button></div>}
    >
      {created && (
        <div className="space-y-3 text-sm">
          <p className="flex items-start gap-2 rounded-card border border-warning/40 bg-warning/10 p-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
            <span>
              <strong>This is the only time you will see this key.</strong> Only a scrambled copy is stored, so it cannot be shown again. Copy it to the tablet now. If you lose it, make a new key.
            </span>
          </p>
          <p className="text-muted">For {created.name}</p>
          <div className="flex items-stretch gap-2">
            <input readOnly value={created.key} aria-label="The kiosk key" onFocus={(e) => e.currentTarget.select()} className="min-h-11 min-w-0 flex-1 select-all rounded-control border border-field-border bg-surface px-3 font-mono text-sm" />
            <Button variant="secondary" onClick={copy} icon={copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}>
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
          {copyFailed && <p role="alert" className="text-danger-soft">Your browser blocked copying. Select the key above and copy it by hand.</p>}
        </div>
      )}
    </Sheet>
  );
};

const CreateSheet: React.FC<{ open: boolean; onClose: () => void; onCreated: (d: DeviceCreated) => void }> = ({ open, onClose, onCreated }) => {
  const stations = useApiQuery(open ? '/api/admin/stations?sort=name&page_size=100' : null, (signal) => apiFetch<StationRows>('/api/admin/stations?sort=name&page_size=100', { signal }));
  const [stationId, setStationId] = useState('');
  const [name, setName] = useState('Station kiosk');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!stationId) return setError('Choose the station this tablet belongs to.');
    if (!name.trim()) return setError('Give the tablet a name.');
    setBusy(true);
    setError(null);
    try {
      onCreated(await apiFetch<DeviceCreated>(`/api/admin/stations/${stationId}/devices`, { method: 'POST', body: { name: name.trim() } }));
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the key.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={open} onClose={onClose} title="Create a kiosk key">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Field label="Station">
          {(p) => (
            <Select value={stationId} onChange={(e) => setStationId(e.target.value)} {...p}>
              <option value="">Choose a station…</option>
              {(stations.data?.items ?? []).map((s) => (
                <option key={s.station_id} value={s.station_id}>{s.name}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Tablet name" hint="For example: Entrance kiosk">{(p) => <TextInput value={name} onChange={(e) => setName(e.target.value)} {...p} />}</Field>
        {error && <p role="alert" className="text-sm font-medium text-danger-soft">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" loading={busy} icon={<KeyRound className="size-4" aria-hidden="true" />}>Create key</Button>
        </div>
      </form>
    </Sheet>
  );
};

const RenameSheet: React.FC<{ device: DeviceRow | null; onClose: () => void; onSaved: () => void }> = ({ device, onClose, onSaved }) => {
  const toast = useToast();
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [shownFor, setShownFor] = useState<string | null>(null);
  // Start from the current name each time a different tablet is picked.
  if (device && shownFor !== device.device_id) {
    setShownFor(device.device_id);
    setName(device.name);
    setError(null);
  }
  if (!device && shownFor !== null) setShownFor(null);
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!device) return;
    if (!name.trim()) return setError('Give the tablet a name.');
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/admin/devices/${device.device_id}`, { method: 'PATCH', body: { name: name.trim() } });
      toast.success('Name saved');
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not rename the tablet.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={device !== null} onClose={onClose} title="Rename this tablet">
      <form onSubmit={save} className="space-y-4" noValidate>
        <Field label="Tablet name" hint={device ? `At ${device.station_name}` : undefined}>{(p) => <TextInput value={name} onChange={(e) => setName(e.target.value)} {...p} />}</Field>
        {error && <p role="alert" className="text-sm font-medium text-danger-soft">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" loading={busy}>Save name</Button>
        </div>
      </form>
    </Sheet>
  );
};

/** Kiosk tablets: when each last asked the server, a new key (shown once), replacing a key, and revoking a lost one. */
export const KiosksPage: React.FC = () => {
  const toast = useToast();
  const query = useApiQuery('/api/admin/devices', (signal) => apiFetch<DeviceRow[]>('/api/admin/devices', { signal }));
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<DeviceCreated | null>(null);
  const [revoking, setRevoking] = useState<DeviceRow | null>(null);
  const [renaming, setRenaming] = useState<DeviceRow | null>(null);
  const [rotating, setRotating] = useState<DeviceRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const revoke = async () => {
    if (!revoking) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/admin/devices/${revoking.device_id}/disable`, { method: 'POST' });
      toast.success(`${revoking.name} is switched off`);
      setRevoking(null);
      query.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not revoke the key.');
    } finally {
      setBusy(false);
    }
  };

  const rotate = async () => {
    if (!rotating) return;
    setBusy(true);
    setError(null);
    try {
      const fresh = await apiFetch<DeviceCreated>(`/api/admin/devices/${rotating.device_id}/rotate`, { method: 'POST' });
      setRotating(null);
      setCreated(fresh); // the new key is shown once, in the same dialog as a brand-new key
      query.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not replace the key.');
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<DeviceRow>[] = [
    {
      id: 'name', header: 'Tablet',
      cell: (r) => (
        <div>
          <p className="font-bold">{r.name}</p>
          <p className="font-mono text-xs text-muted">key ks_{r.key_prefix.replace(/^ks_/, '')}_…</p>
        </div>
      ),
    },
    { id: 'station', header: 'Station', cell: (r) => <span className="block max-w-[16rem] truncate" title={r.station_name}>{r.station_name}</span> },
    { id: 'seen', header: 'Last seen', cell: (r) => (r.last_seen_at ? <DateTime value={r.last_seen_at} /> : <span className="text-muted">never</span>) },
    { id: 'status', header: 'Status', cell: (r) => <Badge tone={r.is_active ? 'primary' : 'neutral'}>{r.is_active ? 'Active' : 'Revoked'}</Badge> },
    {
      id: 'actions', header: 'Actions', align: 'right',
      cell: (r) =>
        r.is_active ? (
          <div className="flex justify-end gap-1">
            <IconButton variant="ghost" onClick={() => setRenaming(r)} aria-label={`Rename ${r.name} at ${r.station_name}`} title="Rename">
              <Pencil className="size-4" aria-hidden="true" />
            </IconButton>
            <Button size="md" variant="ghost" icon={<RefreshCw className="size-4" aria-hidden="true" />} onClick={() => { setError(null); setRotating(r); }} aria-label={`Replace the key of ${r.name} at ${r.station_name}`}>
              New key
            </Button>
            <Button size="md" variant="ghost" icon={<ShieldOff className="size-4" aria-hidden="true" />} onClick={() => { setError(null); setRevoking(r); }} aria-label={`Revoke the key of ${r.name} at ${r.station_name}`}>
              Revoke
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Kiosks"
        subtitle="One tablet per station. A key opens only its own station."
        action={<Button icon={<Plus className="size-4" aria-hidden="true" />} onClick={() => setCreating(true)}>Create key</Button>}
      />
      <QueryState loading={query.loading} error={query.error} hasData={!!query.data} retry={query.retry} rows={3}>
        <DataTable
          caption="Kiosk tablets"
          columns={columns}
          rows={query.data ?? []}
          rowKey={(r) => r.device_id}
          empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">No kiosks yet. Create a key for a station.</p>}
        />
      </QueryState>
      <CreateSheet open={creating} onClose={() => setCreating(false)} onCreated={(d) => { setCreated(d); query.refresh(); }} />
      <KeyDialog created={created} onClose={() => setCreated(null)} />
      <RenameSheet device={renaming} onClose={() => setRenaming(null)} onSaved={query.refresh} />
      <ConfirmDialog open={rotating !== null} title="Replace this key?" confirmLabel="Make a new key" busy={busy} error={error} onClose={() => setRotating(null)} onConfirm={() => void rotate()}>
        <p>
          <strong>{rotating?.name}</strong> at {rotating?.station_name} gets a new key and the <strong>old key stops working at once</strong>. Use this when a key may have leaked, or the tablet was replaced.
        </p>
        <p className="text-muted">The new key is shown once. Paste it on the tablet&apos;s setup screen (press and hold the logo for 3 seconds).</p>
      </ConfirmDialog>
      <ConfirmDialog open={revoking !== null} title="Revoke this key?" confirmLabel="Revoke key" danger busy={busy} error={error} onClose={() => setRevoking(null)} onConfirm={() => void revoke()}>
        <p>
          <strong>{revoking?.name}</strong> at {revoking?.station_name} stops working at once and its setup screen will ask for a new key. This cannot be undone: make a new key to bring a tablet back.
        </p>
      </ConfirmDialog>
    </>
  );
};
