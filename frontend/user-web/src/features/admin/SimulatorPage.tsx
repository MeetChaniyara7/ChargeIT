import React, { useEffect, useState } from 'react';
import { AlertTriangle, CirclePause, Plug, PlugZap, Wrench, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Button, Card, DateTime, Field, Select } from '../../components/ui';
import { ApiError, apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { ChargerStatusBadge, PageHeader, QueryState } from './shared';
import type { AdminStation, ChargerEvent, SimulateResult, StationRows } from './types';

const ACTIONS: { event: string; label: string; hint: string; icon: LucideIcon; tone?: 'danger' }[] = [
  { event: 'EXTERNAL_START', label: 'Simulate external session', hint: 'A driver starts it with the operator’s own app or card. Refused while the charger is reserved.', icon: PlugZap },
  { event: 'EXTERNAL_STOP', label: 'Stop external session', hint: 'That outside session ends.', icon: CirclePause },
  { event: 'UNPLUG', label: 'Unplug', hint: 'Whatever is charging is unplugged: the session ends and is billed up to now.', icon: Plug },
  { event: 'FAULT', label: 'Fault', hint: 'The charger breaks. A running session is stopped.', icon: AlertTriangle, tone: 'danger' },
  { event: 'RECOVER', label: 'Recover', hint: 'A faulted charger is repaired.', icon: Wrench },
];

const POLL_MS = 3000;

/** Make a charger behave like a real one, and watch what it logs. */
export const SimulatorPage: React.FC = () => {
  const stations = useApiQuery('/api/admin/stations?sort=name&page_size=100', (signal) => apiFetch<StationRows>('/api/admin/stations?sort=name&page_size=100', { signal }));
  const [stationId, setStationId] = useState('');
  const [chargerId, setChargerId] = useState('');
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const stationKey = stationId ? `/api/admin/stations/${stationId}` : null;
  const station = useApiQuery(stationKey, (signal) => apiFetch<AdminStation>(stationKey as string, { signal }));
  const eventsKey = chargerId ? `/api/admin/chargers/${chargerId}/events?limit=30` : null;
  const events = useApiQuery(eventsKey, (signal) => apiFetch<ChargerEvent[]>(eventsKey as string, { signal }));
  const charger = station.data?.chargers.find((c) => c.charger_id === chargerId);

  // The log and the charger's status refresh by themselves, so a change from the kiosk or a job shows up here.
  const refreshStation = station.refresh;
  const refreshEvents = events.refresh;
  useEffect(() => {
    if (!chargerId) return;
    const timer = window.setInterval(() => {
      refreshStation();
      refreshEvents();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [chargerId, refreshStation, refreshEvents]);

  const run = async (event: string, label: string) => {
    if (!chargerId) return;
    setBusy(event);
    setResult(null);
    try {
      const out = await apiFetch<SimulateResult>(`/api/admin/chargers/${chargerId}/simulate`, { method: 'POST', body: { event } });
      setResult(out.accepted ? { ok: true, text: `${label}: done. The charger is now ${out.status.toLowerCase().replace('_', ' ')}.` } : { ok: false, text: `${label}: refused. ${out.reason ?? ''}` });
    } catch (e) {
      setResult({ ok: false, text: e instanceof ApiError || e instanceof Error ? e.message : 'That did not work.' });
    } finally {
      setBusy(null);
      refreshStation();
      refreshEvents();
    }
  };

  return (
    <>
      <PageHeader title="Simulator" subtitle="We cannot connect real chargers, so this makes one report what a real one would." />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Station">
          {(p) => (
            <Select value={stationId} onChange={(e) => { setStationId(e.target.value); setChargerId(''); setResult(null); }} {...p}>
              <option value="">Choose a station…</option>
              {(stations.data?.items ?? []).map((s) => (
                <option key={s.station_id} value={s.station_id}>{s.name}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Charger">
          {(p) => (
            <Select value={chargerId} onChange={(e) => { setChargerId(e.target.value); setResult(null); }} disabled={!station.data} {...p}>
              <option value="">{stationId ? 'Choose a charger…' : 'Choose a station first'}</option>
              {(station.data?.chargers ?? []).map((c) => (
                <option key={c.charger_id} value={c.charger_id}>{c.label}</option>
              ))}
            </Select>
          )}
        </Field>
      </div>

      {!chargerId ? (
        <Card className="p-6 text-center text-sm text-muted">Choose a station and a charger to start.</Card>
      ) : (
        <>
          <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
            <p className="text-base font-bold">{charger?.label}</p>
            {charger && <ChargerStatusBadge status={charger.status} />}
          </Card>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {ACTIONS.map(({ event, label, hint, icon: Icon, tone }) => (
              <div key={event} className="flex flex-col gap-1.5">
                <Button size="lg" fullWidth variant={tone === 'danger' ? 'danger' : 'secondary'} loading={busy === event} disabled={busy !== null && busy !== event} icon={<Icon className="size-5" aria-hidden="true" />} onClick={() => void run(event, label)}>
                  {label}
                </Button>
                <p className="text-xs text-muted">{hint}</p>
              </div>
            ))}
          </div>
          <div role="status" aria-live="polite" className="min-h-6">
            {result && <p className={result.ok ? 'text-sm font-medium text-primary' : 'text-sm font-medium text-warning'}>{result.text}</p>}
          </div>

          <section aria-labelledby="log-heading" className="space-y-2">
            <h2 id="log-heading" className="flex items-center gap-2 text-xl font-bold">
              <Zap className="size-5 text-primary" aria-hidden="true" />
              Live event log
            </h2>
            <p className="text-xs text-muted">Newest first. Updates every 3 seconds. A refused request is logged too.</p>
            <QueryState loading={events.loading} error={events.error} hasData={!!events.data} retry={events.retry} rows={2}>
              {events.data && events.data.length === 0 ? (
                <p className="rounded-card border border-border p-6 text-center text-sm text-muted">Nothing has happened on this charger yet.</p>
              ) : (
                <ul className="divide-y divide-border rounded-card border border-border bg-surface">
                  {(events.data ?? []).map((e) => (
                    <li key={e.event_id} className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2 text-sm">
                      <span className={e.event.startsWith('REJECTED') ? 'font-medium text-warning' : 'font-medium'}>{e.event.replaceAll('_', ' ').toLowerCase()}</span>
                      <span className="text-xs text-muted">
                        {e.source.toLowerCase()} · <DateTime value={e.created_at} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </QueryState>
          </section>
        </>
      )}
    </>
  );
};
