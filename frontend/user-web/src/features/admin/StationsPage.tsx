import React, { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import { Badge, buttonClasses, DataTable, Field, Pagination, Select, TextInput } from '../../components/ui';
import type { Column, SortState } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useApiQuery } from '../../lib/useApiQuery';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { PageHeader, QueryState, SourceBadge } from './shared';
import type { StationRow, StationRows } from './types';

const PAGE_SIZE = 20;

/** Searchable, sortable, paginated list of stations. The search, sort and page live in the URL. */
export const StationsPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState('');
  const q = useDebouncedValue(text.trim(), 300); // the search goes to the server only after a short pause
  const sort: SortState = { id: params.get('sort') ?? 'name', dir: params.get('dir') === 'desc' ? 'desc' : 'asc' };
  const active = params.get('active') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);

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

  const key = `/api/admin/stations?${new URLSearchParams({
    ...(q ? { q } : {}),
    sort: sort.id, direction: sort.dir, page: String(page), page_size: String(PAGE_SIZE),
    ...(active ? { active } : {}),
  })}`;
  const query = useApiQuery(key, (signal) => apiFetch<StationRows>(key, { signal }));
  const data = query.data;

  const columns: Column<StationRow>[] = [
    {
      id: 'name', header: 'Name', sortable: true,
      cell: (r) => (
        <Link to={`/admin/stations/${r.station_id}`} className="font-bold text-info hover:underline">
          {r.name}
        </Link>
      ),
    },
    { id: 'city', header: 'City', sortable: true, cell: (r) => r.city ?? <span className="text-muted">—</span> },
    { id: 'operator', header: 'Operator', sortable: true, cell: (r) => r.operator_name ?? <span className="text-muted">—</span> },
    { id: 'source', header: 'Source', sortable: true, cell: (r) => <SourceBadge source={r.data_source} /> },
    { id: 'chargers', header: 'Chargers', sortable: true, align: 'right', cell: (r) => <span className="num">{r.charger_count}</span> },
    { id: 'status', header: 'Status', sortable: true, cell: (r) => <Badge tone={r.is_active ? 'primary' : 'neutral'}>{r.is_active ? 'Active' : 'Inactive'}</Badge> },
  ];

  return (
    <>
      <PageHeader
        title="Stations"
        action={
          <Link to="/admin/stations/new" className={buttonClasses()}>
            <Plus className="size-4" aria-hidden="true" />
            New station
          </Link>
        }
      />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Search" className="min-w-56 flex-1" hint="Station, city or operator name">
          {(p) => (
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
              <TextInput type="search" value={text} onChange={(e) => setText(e.target.value)} className="pl-9" {...p} />
            </div>
          )}
        </Field>
        <Field label="Status" className="w-40">
          {(p) => (
            <Select value={active} onChange={(e) => update({ active: e.target.value, page: null })} {...p}>
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </Select>
          )}
        </Field>
      </div>
      <QueryState loading={query.loading} error={query.error} hasData={!!data} retry={query.retry} rows={5}>
        {data && (
          <div className="space-y-3" aria-busy={query.refreshing}>
            <DataTable
              caption="Stations"
              columns={columns}
              rows={data.items}
              rowKey={(r) => r.station_id}
              sort={sort}
              onSort={(id) => update({ sort: id, dir: sort.id === id && sort.dir === 'asc' ? 'desc' : 'asc', page: null })}
              empty={<p className="rounded-card border border-border p-6 text-center text-sm text-muted">No stations match.</p>}
            />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(n) => update({ page: String(n) })} />
          </div>
        )}
      </QueryState>
    </>
  );
};
