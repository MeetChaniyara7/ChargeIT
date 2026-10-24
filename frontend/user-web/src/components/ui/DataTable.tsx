import type { ReactNode } from 'react';
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { cx } from './cx';

export interface Column<T> {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
  /** Shows a sort button in the header. The id is what `onSort` receives. */
  sortable?: boolean;
  align?: 'left' | 'right';
  className?: string;
}

export interface SortState {
  id: string;
  dir: 'asc' | 'desc';
}

export interface DataTableProps<T> {
  /** Names the table for screen readers (it is not shown). */
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  sort?: SortState;
  onSort?: (id: string) => void;
  /** Shown instead of the table when there are no rows. */
  empty?: ReactNode;
  className?: string;
}

/**
 * A plain, dense table. Sortable columns have a real button in the header (keyboard and screen-reader friendly,
 * `aria-sort` says the order). On a narrow screen the table scrolls sideways inside its box instead of squeezing.
 */
export function DataTable<T>({ caption, columns, rows, rowKey, sort, onSort, empty, className }: DataTableProps<T>) {
  if (rows.length === 0 && empty) return <>{empty}</>;
  return (
    <div className={cx('overflow-x-auto rounded-card border border-border', className)}>
      <table className="w-full min-w-max border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-raised text-xs uppercase tracking-wide text-muted">
          <tr>
            {columns.map((column) => {
              const active = sort?.id === column.id;
              return (
                <th
                  key={column.id}
                  scope="col"
                  aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : column.sortable ? 'none' : undefined}
                  className={cx('whitespace-nowrap px-3 py-2 font-bold', column.align === 'right' && 'text-right', column.className)}
                >
                  {column.sortable && onSort ? (
                    <button
                      type="button"
                      onClick={() => onSort(column.id)}
                      className={cx('-mx-1 inline-flex min-h-11 items-center gap-1 rounded-control px-1 uppercase tracking-wide hover:text-fg', active && 'text-fg')}
                    >
                      {column.header}
                      {active ? (
                        sort.dir === 'asc' ? <ArrowUp className="size-3.5" aria-hidden="true" /> : <ArrowDown className="size-3.5" aria-hidden="true" />
                      ) : (
                        <ChevronsUpDown className="size-3.5 opacity-60" aria-hidden="true" />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.id} className={cx('px-3 py-2 align-middle', column.align === 'right' && 'text-right', column.className)}>
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
