import React, { useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { Button, ConfirmDialog, DataTable, Field, Sheet, TextInput, useToast } from '../../components/ui';
import type { Column } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { PageHeader, QueryState } from './shared';
import type { Operator } from './types';

/** Add or rename an operator (the company that runs a station). */
const OperatorSheet: React.FC<{ operator: Operator | null; open: boolean; onClose: () => void; onSaved: () => void }> = ({ operator, open, onClose, onSaved }) => {
  const toast = useToast();
  const [name, setName] = useState('');
  const [website, setWebsite] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [openedFor, setOpenedFor] = useState<{ open: boolean; operator: Operator | null } | null>(null);

  // Each time the sheet opens it starts from the operator being edited, or blank.
  if (openedFor?.open !== open || openedFor?.operator !== operator) {
    setOpenedFor({ open, operator });
    if (open) {
      setName(operator?.name ?? '');
      setWebsite(operator?.website ?? '');
      setError(null);
      setFieldError(null);
    }
  }

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return setFieldError('Enter the operator name.');
    if (website.trim() && !/^https?:\/\/\S+$/i.test(website.trim())) return setFieldError('The website must start with http:// or https://');
    setBusy(true);
    setError(null);
    setFieldError(null);
    const body = { name: name.trim(), website: website.trim() || null };
    try {
      if (operator) await apiFetch(`/api/admin/operators/${operator.operator_id}`, { method: 'PATCH', body });
      else await apiFetch('/api/admin/operators', { method: 'POST', body });
      toast.success(operator ? 'Operator saved' : 'Operator added');
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the operator.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title={operator ? `Edit ${operator.name}` : 'Add an operator'}>
      <form onSubmit={save} className="space-y-4" noValidate>
        <Field label="Name" error={fieldError}>{(p) => <TextInput value={name} onChange={(e) => setName(e.target.value)} {...p} />}</Field>
        <Field label="Website" hint="Optional, for example https://example.com">{(p) => <TextInput type="url" value={website} onChange={(e) => setWebsite(e.target.value)} {...p} />}</Field>
        {error && <p role="alert" className="text-sm font-medium text-danger-soft">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" loading={busy}>{operator ? 'Save' : 'Add operator'}</Button>
        </div>
      </form>
    </Sheet>
  );
};

/** The companies that run stations. Each station is assigned to one on its edit page. */
export const OperatorsPage: React.FC = () => {
  const toast = useToast();
  const query = useApiQuery('/api/admin/operators', (signal) => apiFetch<Operator[]>('/api/admin/operators', { signal }));
  const [editing, setEditing] = useState<{ open: boolean; operator: Operator | null }>({ open: false, operator: null });
  const [deleting, setDeleting] = useState<Operator | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remove = async () => {
    if (!deleting) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/admin/operators/${deleting.operator_id}`, { method: 'DELETE' });
      toast.success(`${deleting.name} deleted`);
      setDeleting(null);
      query.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the operator.');
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<Operator>[] = [
    { id: 'name', header: 'Operator', cell: (o) => <span className="font-bold">{o.name}</span> },
    { id: 'website', header: 'Website', cell: (o) => (o.website ? <a href={o.website} target="_blank" rel="noopener noreferrer" className="text-info hover:underline">{o.website.replace(/^https?:\/\//, '')}</a> : <span className="text-muted">—</span>) },
    { id: 'stations', header: 'Stations', align: 'right', cell: (o) => <span className="num">{o.station_count}</span> },
    {
      id: 'actions', header: 'Actions', align: 'right',
      cell: (o) => (
        <div className="flex justify-end gap-1">
          <Button size="md" variant="ghost" icon={<Pencil className="size-4" aria-hidden="true" />} onClick={() => setEditing({ open: true, operator: o })} aria-label={`Edit ${o.name}`}>Edit</Button>
          <Button size="md" variant="ghost" icon={<Trash2 className="size-4" aria-hidden="true" />} onClick={() => { setError(null); setDeleting(o); }} aria-label={`Delete ${o.name}`}>Delete</Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Operators"
        subtitle="The companies that run stations. A station is assigned to an operator on its edit page."
        action={<Button icon={<Plus className="size-4" aria-hidden="true" />} onClick={() => setEditing({ open: true, operator: null })}>Add operator</Button>}
      />
      <QueryState loading={query.loading} error={query.error} hasData={!!query.data} retry={query.retry} rows={4}>
        <DataTable
          caption="Operators"
          columns={columns}
          rows={query.data ?? []}
          rowKey={(o) => o.operator_id}
          empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">No operators yet.</p>}
        />
      </QueryState>
      <OperatorSheet operator={editing.operator} open={editing.open} onClose={() => setEditing((e) => ({ ...e, open: false }))} onSaved={query.refresh} />
      <ConfirmDialog open={deleting !== null} title="Delete this operator?" confirmLabel="Delete operator" danger busy={busy} error={error} onClose={() => setDeleting(null)} onConfirm={() => void remove()}>
        <p>
          <strong>{deleting?.name}</strong> will be removed.
          {deleting && deleting.station_count > 0 ? ` It still has ${deleting.station_count} station${deleting.station_count === 1 ? '' : 's'}: move ${deleting.station_count === 1 ? 'it' : 'them'} to another operator first, or the delete will be refused.` : ' It has no stations, so nothing else changes.'}
        </p>
      </ConfirmDialog>
    </>
  );
};
