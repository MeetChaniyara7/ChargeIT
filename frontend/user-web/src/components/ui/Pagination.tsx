import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './Button';

export interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}

/** "21-40 of 84" with Previous and Next. Hidden when everything fits on one page. */
export function Pagination({ page, pageSize, total, onPage }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return <p className="text-xs text-muted">{total} {total === 1 ? 'result' : 'results'}</p>;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center justify-between gap-3">
      <p className="num text-sm text-muted" aria-live="polite">
        {first}-{last} of {total}
      </p>
      <div className="flex items-center gap-2">
        <Button size="md" variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)} icon={<ChevronLeft className="size-4" aria-hidden="true" />}>
          Previous
        </Button>
        <span className="num text-sm text-muted">
          Page {page} of {pages}
        </span>
        <Button size="md" variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
          <ChevronRight className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
