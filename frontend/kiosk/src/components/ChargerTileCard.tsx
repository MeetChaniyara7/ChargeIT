import { Check, Zap } from 'lucide-react';
import type { ChargerTile } from '../lib/api';
import { tileText } from '../lib/tiles';
import type { Tone } from '../lib/tiles';
import { rupees } from '../lib/format';
import { ConnectorIcon } from './ConnectorIcon';
import { cx } from './cx';

// Each state has a label in words AND a colour, so nobody depends on colour alone.
const TONES: Record<Tone, { border: string; pill: string }> = {
  free: { border: 'border-primary/60', pill: 'bg-primary text-on-primary' },
  reserved: { border: 'border-warning/60', pill: 'bg-warning text-black' },
  charging: { border: 'border-info/60', pill: 'bg-info text-black' },
  paying: { border: 'border-warning/60', pill: 'bg-warning text-black' },
  down: { border: 'border-danger/60', pill: 'bg-danger-strong text-white' },
};

/** One charger on the status board. It shows no names, phone numbers or bills of app users. */
export function ChargerTileCard({ tile }: { tile: ChargerTile }) {
  const text = tileText(tile);
  const tone = TONES[text.tone];
  const progress = tile.state === 'CHARGING' && tile.progress_percent != null ? Math.round(tile.progress_percent) : null;
  return (
    <article className={cx('flex flex-col justify-between gap-3 rounded-card border-2 bg-surface p-5', tone.border)} aria-label={`Charger ${tile.label}: ${text.label}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-3xl font-extrabold leading-none">{tile.label}</p>
          <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-lg text-muted">
            <ConnectorIcon type={tile.connector_type} className="text-fg" />
            {tile.power_kw != null && (
              <span className="inline-flex items-center gap-1">
                <Zap className="size-4" aria-hidden="true" />
                {tile.power_kw} kW
              </span>
            )}
            {tile.price_per_kwh != null && <span className="num">{rupees(tile.price_per_kwh)}/kWh</span>}
          </p>
        </div>
        <span className={cx('shrink-0 rounded-full px-4 py-1.5 text-lg font-extrabold', tone.pill)}>{text.label}</span>
      </div>

      <div className="space-y-2">
        {progress !== null && (
          <div className="flex items-center gap-3">
            <div className="h-4 flex-1 overflow-hidden rounded-full bg-raised" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Battery charged">
              <div className="h-full rounded-full bg-info" style={{ width: `${progress}%` }} />
            </div>
            <span className="num w-14 text-right text-xl font-bold">{progress}%</span>
          </div>
        )}
        {text.lines.map((line) => (
          <p key={line} className="text-xl font-medium">
            {line}
          </p>
        ))}
        {text.done && (
          <p className="flex items-center gap-2 text-xl font-bold text-primary">
            <Check className="size-5" aria-hidden="true" />
            {text.done}
          </p>
        )}
      </div>
    </article>
  );
}
