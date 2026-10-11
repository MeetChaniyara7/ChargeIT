import { useRef } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { cx } from './cx';

export interface TabItem {
  id: string;
  label: string;
  /** A small number shown next to the label, e.g. unpaid bills. Hidden when 0 or missing. */
  count?: number;
}

export interface TabsProps {
  tabs: TabItem[];
  value: string;
  onChange: (id: string) => void;
  /** Names the tab list for screen readers, e.g. "Booking status". */
  label: string;
  className?: string;
}

const tabId = (id: string) => `tab-${id}`;
const panelId = (id: string) => `tabpanel-${id}`;

/**
 * A row of tabs. Keyboard: Left/Right arrows move between tabs, Home/End jump to the
 * first/last. Pair with <TabPanel> for the content.
 */
export function Tabs({ tabs, value, onChange, label, className }: TabsProps) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const move = (index: number) => {
    const next = tabs[(index + tabs.length) % tabs.length];
    onChange(next.id);
    refs.current[next.id]?.focus();
  };

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    if (event.key === 'ArrowRight') move(index + 1);
    else if (event.key === 'ArrowLeft') move(index - 1);
    else if (event.key === 'Home') move(0);
    else if (event.key === 'End') move(tabs.length - 1);
    else return;
    event.preventDefault();
  };

  return (
    <div role="tablist" aria-label={label} className={cx('flex gap-1 border-b border-border', className)}>
      {tabs.map((tab, index) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[tab.id] = el;
            }}
            role="tab"
            id={tabId(tab.id)}
            type="button"
            aria-selected={selected}
            aria-controls={panelId(tab.id)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => onKeyDown(e, index)}
            className={cx(
              '-mb-px inline-flex min-h-11 items-center gap-2 border-b-2 px-4 text-sm font-bold transition-colors',
              selected ? 'border-primary text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            {tab.label}
            {tab.count ? (
              <span className="rounded-full bg-warning/15 px-1.5 text-xs text-warning">{tab.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/** The content for one tab. Only the selected tab's panel is shown. */
export function TabPanel({ id, value, children, className }: { id: string; value: string; children: ReactNode; className?: string }) {
  return (
    <div role="tabpanel" id={panelId(id)} aria-labelledby={tabId(id)} hidden={id !== value} className={className}>
      {id === value ? children : null}
    </div>
  );
}
