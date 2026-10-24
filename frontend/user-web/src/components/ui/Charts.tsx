import { cx } from './cx';

export interface ChartPoint {
  label: string;
  value: number;
  /** A longer name for screen readers and the hover title, e.g. "Mon 12 Oct". */
  title?: string;
}

/**
 * Columns drawn with plain SVG (no chart library). The numbers are also in an off-screen table-like list,
 * so a screen reader gets every value, and each column has a hover title.
 */
export function ColumnChart({ data, label, className }: { data: ChartPoint[]; label: string; className?: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const width = 100;
  const height = 48;
  const gap = 1.5;
  const bar = (width - gap * (data.length - 1)) / Math.max(data.length, 1);
  return (
    <figure className={cx("min-w-0", className)}>
      <svg viewBox={`0 0 ${width} ${height + 8}`} role="img" aria-label={label} className="h-44 w-full text-primary" preserveAspectRatio="none">
        <line x1="0" y1={height} x2={width} y2={height} stroke="currentColor" strokeOpacity="0.3" strokeWidth="0.3" />
        {data.map((d, i) => {
          const h = (d.value / max) * (height - 4);
          return (
            <g key={d.label + i}>
              <title>{`${d.title ?? d.label}: ${d.value}`}</title>
              <rect x={i * (bar + gap)} y={height - h} width={bar} height={Math.max(h, d.value > 0 ? 0.6 : 0)} rx="0.6" fill="currentColor" />
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-xs text-muted" aria-hidden="true">
        <span>{data[0]?.label}</span>
        <span>max {max}</span>
        <span>{data[data.length - 1]?.label}</span>
      </div>
      <ul className="sr-only">
        {data.map((d, i) => (
          <li key={d.label + i}>
            {d.title ?? d.label}: {d.value}
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Horizontal bars with the name and number on each line (for "no-shows per station"). */
export function BarList({ data, className, tone = 'danger' }: { data: ChartPoint[]; className?: string; tone?: 'primary' | 'danger' }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className={cx('min-w-0 space-y-2', className)}>
      {data.map((d, i) => (
        <li key={d.label + i} className="min-w-0">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate">{d.label}</span>
            <span className="num font-bold">{d.value}</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-raised" aria-hidden="true">
            <div className={cx('h-full rounded-full', tone === 'danger' ? 'bg-danger' : 'bg-primary')} style={{ width: `${(d.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
