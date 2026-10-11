import React, { useEffect, useId, useRef, useState } from 'react';
import { ArrowLeft, Building2, Clock, LocateFixed, MapPin, Search, Sparkles, X, Zap } from 'lucide-react';
import type { ParsedSearch, SearchToken } from '@chargespot/shared';
import { availabilityFor, IconButton, Spinner, StatusBadge, cx } from '../../components/ui';
import { FAST_KW } from './constants';
import type { AreaSuggestion, StationSummary, SuggestResponse } from './types';
import type { ExploreFilters } from './useExploreFilters';

const EXAMPLES = ['fast CCS2 near Bopal', 'Tata Power open now', 'cheap Type 2 in Gandhinagar'];

interface SuggestionOption {
  id: string;
  group: 'fix' | 'stations' | 'operators' | 'cities' | 'places' | 'recent' | 'examples';
  icon: React.ReactNode;
  label: string;
  detail?: React.ReactNode;
  pick: () => void;
  /** Stay open after picking (e.g. a spelling fix: the user keeps going). */
  keepOpen?: boolean;
}

const GROUP_TITLES: Record<SuggestionOption['group'], string | null> = {
  fix: null,
  stations: 'Stations',
  operators: 'Operators',
  cities: 'Cities',
  places: 'Places',
  recent: 'Recent',
  examples: 'Try',
};

export interface SearchBoxProps {
  value: string;
  onChange: (text: string) => void;
  /** Enter: apply the understood filters and find the station, operator or place. */
  onSubmit: (text: string) => void;
  parsed: ParsedSearch;
  onRemoveToken: (token: SearchToken) => void;
  suggestions: SuggestResponse | undefined;
  suggestLoading: boolean;
  suggestError: string | null;
  recent: string[];
  onClearRecent: () => void;
  onPickStation: (station: StationSummary) => void;
  onPickArea: (kind: 'operator' | 'city', area: AreaSuggestion) => void;
  filters: ExploreFilters;
  onFiltersChange: (change: Partial<ExploreFilters>) => void;
  onLocate: () => void;
  locating: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Phones: while open, the search fills the screen (bigger targets, room for the keyboard). */
  fullScreen: boolean;
}

/**
 * The Explore search box: an accessible combobox (WAI-ARIA 1.2 pattern).
 * - Typing shows what was understood ("Understood" chips) and suggestions from our own
 *   stations, operators and cities. Places are only looked up when Enter is pressed.
 * - Keyboard: Down/Up move through suggestions, Enter picks one (or searches), Esc closes.
 */
export const SearchBox: React.FC<SearchBoxProps> = (props) => {
  const {
    value, onChange, onSubmit, parsed, onRemoveToken, suggestions, suggestLoading, suggestError, recent, onClearRecent,
    onPickStation, onPickArea, filters, onFiltersChange, onLocate, locating, open, onOpenChange, fullScreen,
  } = props;
  const baseId = useId();
  const listId = `${baseId}-list`;
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [active, setActive] = useState(-1);

  const text = parsed.text;
  const empty = value.trim() === '';
  const close = () => {
    onOpenChange(false);
    setActive(-1);
  };
  const choose = (pick: () => void) => {
    close();
    inputRef.current?.blur();
    pick();
  };

  // ---- the options, in display order ----
  const options: SuggestionOption[] = [];
  if (suggestions?.did_you_mean) {
    const fixed = suggestions.did_you_mean;
    options.push({
      id: 'fix', group: 'fix', icon: <Sparkles className="size-4" aria-hidden="true" />,
      label: `Did you mean ${fixed}?`,
      // Swap the misspelt words for the fix and keep any filter words, e.g. "tata powr open" -> "Tata Power open".
      pick: () => onChange(text && value.includes(text) ? value.replace(text, fixed) : fixed),
      keepOpen: true,
    });
  }
  suggestions?.stations.forEach((s) =>
    options.push({
      id: `station-${s.station_id}`, group: 'stations', icon: <Zap className="size-4" aria-hidden="true" />,
      label: s.name,
      detail: (
        <>
          <span className="truncate">{s.city || s.address || s.operator_name || ''}</span>
          <StatusBadge className="shrink-0" status={availabilityFor(s.charger_free, s.charger_total)}
            label={s.charger_total > 0 ? `${s.charger_free}/${s.charger_total} free` : 'No chargers'} />
        </>
      ),
      pick: () => onPickStation(s),
    }),
  );
  suggestions?.operators.forEach((o) =>
    options.push({
      id: `operator-${o.name}`, group: 'operators', icon: <Building2 className="size-4" aria-hidden="true" />,
      label: o.name, detail: <span className="num">{o.station_count} station{o.station_count === 1 ? '' : 's'}</span>,
      pick: () => onPickArea('operator', o),
    }),
  );
  suggestions?.cities.forEach((c) =>
    options.push({
      id: `city-${c.name}`, group: 'cities', icon: <MapPin className="size-4" aria-hidden="true" />,
      label: c.name, detail: <span className="num">{c.station_count} station{c.station_count === 1 ? '' : 's'}</span>,
      pick: () => onPickArea('city', c),
    }),
  );
  if (text.length >= 2) {
    options.push({
      id: 'places', group: 'places', icon: <Search className="size-4" aria-hidden="true" />,
      label: `Search places for “${text}”`, detail: <span>Press Enter</span>,
      pick: () => onSubmit(value),
    });
  }
  if (empty) {
    recent.forEach((r, i) =>
      options.push({ id: `recent-${i}`, group: 'recent', icon: <Clock className="size-4" aria-hidden="true" />, label: r, pick: () => onSubmit(r) }),
    );
    EXAMPLES.forEach((example, i) =>
      options.push({ id: `example-${i}`, group: 'examples', icon: <Search className="size-4" aria-hidden="true" />, label: example, pick: () => onSubmit(example) }),
    );
  }
  const pickOption = (option: SuggestionOption) => {
    if (option.keepOpen) {
      option.pick();
      setActive(-1);
      inputRef.current?.focus();
    } else {
      choose(option.pick);
    }
  };
  const optionId = (option: SuggestionOption) => `${baseId}-${option.id}`;
  const activeOption = active >= 0 ? options[active] : undefined;

  // Keep the highlighted suggestion in view.
  useEffect(() => {
    if (activeOption) document.getElementById(optionId(activeOption))?.scrollIntoView({ block: 'nearest' });
    // optionId only depends on ids that are in activeOption.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeOption?.id]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (!open) onOpenChange(true);
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, -1));
    } else if (event.key === 'Enter' && open && activeOption) {
      event.preventDefault();
      pickOption(activeOption);
    } else if (event.key === 'Escape' && open) {
      event.preventDefault();
      close();
      if (fullScreen) inputRef.current?.blur();
    }
  };

  // Desktop: close when focus leaves the search entirely (a click elsewhere, or Tab away).
  const onBlur = (event: React.FocusEvent) => {
    if (!fullScreen && !containerRef.current?.contains(event.relatedTarget as Node | null)) close();
  };

  const expanded = open && fullScreen;
  const resultCount = options.filter((o) => ['stations', 'operators', 'cities'].includes(o.group)).length;

  const groups = (Object.keys(GROUP_TITLES) as SuggestionOption['group'][])
    .map((group) => ({ group, items: options.filter((o) => o.group === group) }))
    .filter(({ items }) => items.length > 0);

  const quickChip = (label: string, selected: boolean, onClick: () => void, icon?: React.ReactNode) => (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={cx(
        'inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full border px-3 text-sm font-medium',
        selected ? 'border-primary bg-primary/15 text-primary' : 'border-field-border bg-surface text-fg hover:bg-raised',
      )}
    >
      {icon}
      {label}
    </button>
  );

  return (
    <div
      ref={containerRef}
      onBlur={onBlur}
      className={cx(expanded && 'fixed inset-0 z-50 flex flex-col gap-3 bg-bg p-3 pt-[max(env(safe-area-inset-top),0.75rem)]')}
    >
      <form
        role="search"
        className={cx('flex items-center gap-0.5 p-1', expanded ? 'rounded-full border border-border bg-surface' : 'liquid-glass')}
        onSubmit={(e) => {
          e.preventDefault();
          choose(() => onSubmit(value));
        }}
      >
        {expanded && (
          <IconButton
            aria-label="Close search"
            onClick={() => {
              close();
              inputRef.current?.blur();
            }}
          >
            <ArrowLeft className="size-5" aria-hidden="true" />
          </IconButton>
        )}
        <label htmlFor={`${baseId}-input`} className="sr-only">
          Search stations, operators, plug types or places
        </label>
        <div className="relative min-w-0 flex-1">
          {!expanded && <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg/70" aria-hidden="true" />}
          <input
            ref={inputRef}
            id={`${baseId}-input`}
            type="search"
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={activeOption ? optionId(activeOption) : undefined}
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              setActive(-1);
              if (!open) onOpenChange(true);
            }}
            onFocus={() => onOpenChange(true)}
            onClick={() => onOpenChange(true)}
            onKeyDown={onKeyDown}
            enterKeyHint="search"
            autoComplete="off"
            spellCheck={false}
            placeholder="Station, operator, plug or place"
            className={cx(
              'w-full rounded-full bg-transparent pr-9 text-fg placeholder:text-fg/60 focus:outline-none [&::-webkit-search-cancel-button]:hidden',
              // Compact over the map; full size (16px text stops iOS zooming in) when it fills the phone screen.
              expanded ? 'min-h-11 pl-3 text-base' : 'min-h-9 pl-9 text-base lg:text-sm',
            )}
          />
          {value && (
            <IconButton
              aria-label="Clear search"
              className={cx('absolute right-0 top-0 rounded-full', !expanded && 'size-9!')}
              onClick={() => {
                onChange('');
                setActive(-1);
                inputRef.current?.focus();
              }}
            >
              <X className="size-4" aria-hidden="true" />
            </IconButton>
          )}
        </div>
        <IconButton
          aria-label="Show my location"
          className={cx('shrink-0 rounded-full', !expanded && 'size-9!')}
          onClick={() => choose(onLocate)}
          disabled={locating}
        >
          {locating ? <Spinner className="size-5" /> : <LocateFixed className="size-5" aria-hidden="true" />}
        </IconButton>
      </form>

      <p className="sr-only" aria-live="polite">
        {open && !empty && !suggestLoading ? `${resultCount} suggestion${resultCount === 1 ? '' : 's'}` : ''}
      </p>

      {open && (
        <div
          className={cx(
            'overflow-y-auto overscroll-contain',
            expanded ? 'min-h-0 flex-1' : 'liquid-glass liquid-glass--panel mt-2 max-h-[min(60vh,30rem)] p-2',
          )}
        >
          {parsed.tokens.length > 0 && (
            <div className="mb-2 px-1">
              <p className="mb-1 text-xs font-bold uppercase tracking-wide text-muted">Understood</p>
              <ul className="flex flex-wrap gap-2">
                {parsed.tokens.map((token, i) => (
                  <li key={`${token.kind}-${i}`}>
                    <button
                      type="button"
                      onClick={() => {
                        onRemoveToken(token);
                        inputRef.current?.focus();
                      }}
                      aria-label={`Remove ${token.label}`}
                      className="inline-flex min-h-9 items-center gap-1 rounded-full border border-primary/40 bg-primary/15 pl-3 pr-2 text-sm font-medium text-primary hover:bg-primary/25"
                    >
                      {token.kind === 'place' && <MapPin className="size-3.5" aria-hidden="true" />}
                      {token.label}
                      <X className="size-3.5" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {empty && (
            <div role="group" aria-label="Quick filters" className="scroll-x-hidden mb-2 flex gap-2 px-1">
              {quickChip('Near me', false, () => choose(onLocate), <LocateFixed className="size-4" aria-hidden="true" />)}
              {quickChip(`Fast ${FAST_KW} kW+`, filters.fast, () => onFiltersChange({ fast: !filters.fast }))}
              {quickChip('Open now', filters.openNow, () => onFiltersChange({ openNow: !filters.openNow }))}
              {quickChip('CCS2', filters.connectors.includes('CCS2'), () =>
                onFiltersChange({
                  connectors: filters.connectors.includes('CCS2') ? filters.connectors.filter((c) => c !== 'CCS2') : [...filters.connectors, 'CCS2'],
                }),
              )}
            </div>
          )}

          <div id={listId} role="listbox" aria-label="Search suggestions">
            {groups.map(({ group, items }) => (
              <div key={group} role="group" aria-labelledby={GROUP_TITLES[group] ? `${baseId}-${group}` : undefined} aria-label={GROUP_TITLES[group] ? undefined : 'Spelling'} className="mb-1">
                {GROUP_TITLES[group] && (
                  <div id={`${baseId}-${group}`} role="presentation" className="px-2 pb-1 pt-2 text-xs font-bold uppercase tracking-wide text-muted">
                    {GROUP_TITLES[group]}
                  </div>
                )}
                {items.map((option) => {
                  const isActive = option === activeOption;
                  return (
                    <div
                      key={option.id}
                      id={optionId(option)}
                      role="option"
                      aria-selected={isActive}
                      // Keep focus in the input so typing can continue after a click.
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pickOption(option)}
                      onMouseMove={() => setActive(options.indexOf(option))}
                      className={cx(
                        'flex min-h-11 cursor-pointer items-center gap-3 rounded-control px-2 py-1.5',
                        isActive ? 'bg-raised ring-1 ring-primary/50' : 'hover:bg-raised',
                        option.group === 'fix' && 'font-bold text-info',
                      )}
                    >
                      <span className="shrink-0 text-muted">{option.icon}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{option.label}</span>
                        {option.detail && <span className="flex items-center justify-between gap-2 text-xs text-muted">{option.detail}</span>}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          {empty && recent.length > 0 && (
            <button type="button" onClick={onClearRecent} className="ml-2 mt-1 min-h-9 text-xs font-bold text-info underline-offset-2 hover:underline">
              Clear recent searches
            </button>
          )}

          {!empty && suggestLoading && (
            <p className="flex items-center gap-2 px-2 py-2 text-sm text-muted">
              <Spinner className="size-4" /> Looking for matches…
            </p>
          )}
          {!empty && !suggestLoading && suggestError && (
            <p className="px-2 py-2 text-sm text-muted">Suggestions are unavailable right now. Press Enter to search.</p>
          )}
          {!empty && !suggestLoading && !suggestError && text.length >= 2 && resultCount === 0 && !suggestions?.did_you_mean && (
            <p className="px-2 py-2 text-sm text-muted">No stations, operators or cities match “{text}”. Press Enter to look for a place.</p>
          )}
          {!empty && text.length < 2 && parsed.tokens.length > 0 && (
            <p className="px-2 py-2 text-sm text-muted">Press Enter to apply these filters.</p>
          )}
        </div>
      )}
    </div>
  );
};
