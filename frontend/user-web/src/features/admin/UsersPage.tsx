import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, ShieldCheck, ShieldOff } from 'lucide-react';
import { Badge, Button, ConfirmDialog, DataTable, DateTime, Field, Pagination, Select, TextInput, useToast } from '../../components/ui';
import type { Column } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { PageHeader, QueryState } from './shared';
import type { UserRow, UserRows } from './types';

const PAGE_SIZE = 20;
const SIGN_IN: Record<string, string> = { GOOGLE: 'Google', PASSWORD: 'Email and password', BOTH: 'Google and password' };

/** Accounts and their roles. An admin can make someone an admin or an ordinary driver again, but not change their own role. */
export const UsersPage: React.FC = () => {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState('');
  const q = useDebouncedValue(text.trim(), 300);
  const role = params.get('role') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const [target, setTarget] = useState<{ user: UserRow; to: 'ADMIN' | 'USER' } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (changes: Record<string, string | null>) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [k, v] of Object.entries(changes)) {
          if (v === null || v === '') next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: true },
    );

  // A new search starts again from the first page.
  const searched = useRef(q);
  useEffect(() => {
    if (searched.current !== q) {
      searched.current = q;
      setParams((previous) => {
        const next = new URLSearchParams(previous);
        next.delete('page');
        return next;
      }, { replace: true });
    }
  }, [q, setParams]);

  const key = `/api/admin/users?${new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), ...(q ? { q } : {}), ...(role ? { role } : {}) })}`;
  const query = useApiQuery(key, (signal) => apiFetch<UserRows>(key, { signal }));
  const data = query.data;

  const confirm = async () => {
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/admin/users/${target.user.user_id}/role`, { method: 'PATCH', body: { role: target.to } });
      toast.success(target.to === 'ADMIN' ? `${target.user.email} is now an admin` : `${target.user.email} is an ordinary driver again`);
      setTarget(null);
      query.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change the role.');
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<UserRow>[] = [
    {
      id: 'user', header: 'Account',
      cell: (u) => (
        <div className="min-w-0">
          <p className="font-bold">
            {u.full_name || u.email}
            {u.is_you && <Badge tone="info" className="ml-2">You</Badge>}
          </p>
          {u.full_name && <p className="text-xs text-muted">{u.email}</p>}
        </div>
      ),
    },
    { id: 'signin', header: 'Signs in with', cell: (u) => SIGN_IN[u.sign_in] ?? u.sign_in },
    { id: 'bookings', header: 'Bookings', align: 'right', cell: (u) => <span className="num">{u.bookings}</span> },
    { id: 'joined', header: 'Joined', cell: (u) => <DateTime value={u.created_at} format="date" /> },
    { id: 'role', header: 'Role', cell: (u) => <Badge tone={u.role === 'ADMIN' ? 'primary' : 'neutral'}>{u.role === 'ADMIN' ? 'Admin' : 'Driver'}</Badge> },
    {
      id: 'actions', header: 'Actions', align: 'right',
      cell: (u) =>
        u.is_you ? (
          <span className="text-xs text-muted">Ask another admin to change your role</span>
        ) : u.role === 'ADMIN' ? (
          <Button size="md" variant="ghost" icon={<ShieldOff className="size-4" aria-hidden="true" />} onClick={() => { setError(null); setTarget({ user: u, to: 'USER' }); }} aria-label={`Remove admin rights from ${u.email}`}>
            Remove admin
          </Button>
        ) : (
          <Button size="md" variant="secondary" icon={<ShieldCheck className="size-4" aria-hidden="true" />} onClick={() => { setError(null); setTarget({ user: u, to: 'ADMIN' }); }} aria-label={`Make ${u.email} an admin`}>
            Make admin
          </Button>
        ),
    },
  ];

  return (
    <>
      <PageHeader title="Users and roles" subtitle={data ? `${data.total} account${data.total === 1 ? '' : 's'}, ${data.admins} admin${data.admins === 1 ? '' : 's'}. Admins can open this area.` : undefined} />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Search" className="min-w-56 flex-1" hint="Email or name">
          {(p) => (
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
              <TextInput type="search" value={text} onChange={(e) => setText(e.target.value)} className="pl-9" {...p} />
            </div>
          )}
        </Field>
        <Field label="Role" className="w-40">
          {(p) => (
            <Select value={role} onChange={(e) => update({ role: e.target.value, page: null })} {...p}>
              <option value="">Everyone</option>
              <option value="ADMIN">Admins</option>
              <option value="USER">Drivers</option>
            </Select>
          )}
        </Field>
      </div>
      <QueryState loading={query.loading} error={query.error} hasData={!!data} retry={query.retry} rows={5}>
        {data && (
          <div className="space-y-3" aria-busy={query.refreshing}>
            <DataTable
              caption="Accounts and roles"
              columns={columns}
              rows={data.items}
              rowKey={(u) => u.user_id}
              empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">No accounts match.</p>}
            />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(n) => update({ page: String(n) })} />
          </div>
        )}
      </QueryState>
      <ConfirmDialog
        open={target !== null}
        title={target?.to === 'ADMIN' ? 'Make this account an admin?' : 'Remove admin rights?'}
        confirmLabel={target?.to === 'ADMIN' ? 'Make admin' : 'Remove admin rights'}
        danger={target?.to === 'USER'}
        busy={busy}
        error={error}
        onClose={() => setTarget(null)}
        onConfirm={() => void confirm()}
      >
        {target?.to === 'ADMIN' ? (
          <p>
            <strong>{target.user.email}</strong> will be able to open the admin area: manage stations, chargers, kiosk keys and other admins, cancel bookings with refunds, and see every booking and payment.
            They need to reload the app to see the Admin link.
          </p>
        ) : (
          <p>
            <strong>{target?.user.email}</strong> will become an ordinary driver and lose access to the admin area. The change is written to the activity log.
          </p>
        )}
      </ConfirmDialog>
    </>
  );
};
