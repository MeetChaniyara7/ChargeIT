// Reads a search typed on Explore, e.g. "fast ccs2 near Bopal", into filters plus the
// leftover text (a station, operator or place name). Pure functions: no network, no DOM.
//
// Rule: never guess. A word becomes a filter only when it is one of the known words
// below; anything else stays in `text`.

import {
  AC_CONNECTORS, CHEAP_MAX_PRICE_INR, CONNECTOR_LABELS, DC_CONNECTORS, FAST_POWER_KW,
} from './constants.ts';
import type { ConnectorType } from './constants.ts';

export type SearchTokenKind = 'connector' | 'fast' | 'power' | 'open' | 'price' | 'nearMe' | 'place';

/** One thing the parser understood, shown as a removable "Understood" chip. */
export interface SearchToken {
  kind: SearchTokenKind;
  label: string;
  /** The parts of the typed text this token came from, as [start, end) offsets. */
  ranges: [number, number][];
}

export interface ParsedSearch {
  connectors: ConnectorType[];
  fast: boolean;
  minPowerKw?: number;
  openNow: boolean;
  maxPricePerKwh?: number;
  nearMe: boolean;
  /** What is left once the known words are taken out, e.g. "Bopal" or "Tata Power". */
  text: string;
  /** True when the user typed "near X" or "in X": the leftover text is a place. */
  placeHint: boolean;
  tokens: SearchToken[];
}

// Word edges that work for any language and for numbers ("ccs3" is not "ccs").
const START = '(?<![\\p{L}\\p{N}])';
const END = '(?![\\p{L}\\p{N}])';
const SEP = '[\\s-]*';
const NUMBER = '(\\d+(?:\\.\\d+)?)';
const RUPEE = '(?:₹|rs\\.?|inr)';

/** Spellings people type for each plug. Keyed by the shared connector list, so it cannot drift. */
const CONNECTOR_SPELLINGS: Record<Exclude<ConnectorType, 'OTHER'>, string[]> = {
  BHARAT_AC001: [`bharat${SEP}ac(?:${SEP}0*01)?`, `ac${SEP}0*01`],
  BHARAT_DC001: [`bharat${SEP}dc(?:${SEP}0*01)?`, `dc${SEP}0*01`, `gb${SEP}/?${SEP}t`],
  CCS2: [`ccs${SEP}2`, 'ccs', `combo(?:${SEP}2)?`],
  TYPE2: [`type${SEP}2`, 'mennekes'],
  TYPE1: [`type${SEP}1`, 'j1772'],
  CHADEMO: [`cha${SEP}de${SEP}mo`],
};

// Filler words that are neither a filter nor a name ("fast chargers near Bopal").
const FILLER = ['chargers?', 'charging', 'stations?', 'points?', 'ev', 'plugs?', 'with', 'and', 'for', 'the', 'an?', 'show', 'find'];

interface Rule {
  pattern: string;
  apply: (match: RegExpExecArray, out: ParsedSearch, range: [number, number]) => void;
}

const addToken = (out: ParsedSearch, kind: SearchTokenKind, label: string, range: [number, number]) =>
  out.tokens.push({ kind, label, ranges: [range] });

const addConnectors = (out: ParsedSearch, types: readonly ConnectorType[]) => {
  for (const type of types) if (!out.connectors.includes(type)) out.connectors.push(type);
};

const PREPOSITION = 'near|in|around|close to';

// Order matters: longer phrases first ("bharat dc" before "dc", "near me" before "near").
const RULES: Rule[] = [
  ...Object.entries(CONNECTOR_SPELLINGS).map(([type, spellings]): Rule => ({
    pattern: spellings.join('|'),
    apply: (_m, out, range) => {
      addConnectors(out, [type as ConnectorType]);
      addToken(out, 'connector', CONNECTOR_LABELS[type as ConnectorType], range);
    },
  })),
  {
    pattern: 'dc',
    apply: (_m, out, range) => {
      addConnectors(out, DC_CONNECTORS);
      addToken(out, 'connector', 'DC plugs', range);
    },
  },
  {
    pattern: 'ac',
    apply: (_m, out, range) => {
      addConnectors(out, AC_CONNECTORS);
      addToken(out, 'connector', 'AC plugs', range);
    },
  },
  {
    pattern: `${NUMBER}${SEP}kw\\+?`,
    apply: (m, out, range) => {
      const kw = Number(m[1]);
      if (!(kw > 0)) return;
      out.minPowerKw = Math.max(out.minPowerKw ?? 0, kw);
      addToken(out, 'power', `${kw} kW+`, range);
    },
  },
  {
    pattern: 'fast|rapid|quick',
    apply: (_m, out, range) => {
      out.fast = true;
      addToken(out, 'fast', `Fast ${FAST_POWER_KW} kW+`, range);
    },
  },
  {
    pattern: 'open\\s*now|open|always\\s*open|24\\s*[x/×]\\s*7|24\\s*(?:hours|hrs?|h)',
    apply: (_m, out, range) => {
      out.openNow = true;
      addToken(out, 'open', 'Open now', range);
    },
  },
  {
    pattern: `(?:under|below|less\\s*than|up\\s*to|upto|max|within)\\s*${RUPEE}?\\s*${NUMBER}(?:\\s*${RUPEE})?(?:\\s*(?:/|per)\\s*kwh)?`,
    apply: (m, out, range) => {
      const price = Number(m[1]);
      if (!(price > 0)) return;
      out.maxPricePerKwh = Math.min(out.maxPricePerKwh ?? Infinity, price);
      addToken(out, 'price', `Under ₹${price}/kWh`, range);
    },
  },
  {
    pattern: 'cheap(?:est)?|budget|low\\s*cost',
    apply: (_m, out, range) => {
      out.maxPricePerKwh = Math.min(out.maxPricePerKwh ?? Infinity, CHEAP_MAX_PRICE_INR);
      addToken(out, 'price', `Under ₹${CHEAP_MAX_PRICE_INR}/kWh`, range);
    },
  },
  {
    pattern: 'near\\s*me|near\\s*by|nearby|nearest|around\\s*me|close\\s*to\\s*me|close\\s*by',
    apply: (_m, out, range) => {
      out.nearMe = true;
      addToken(out, 'nearMe', 'Near me', range);
    },
  },
];

const compile = (pattern: string) => new RegExp(`${START}(?:${pattern})${END}`, 'giu');
const COMPILED = RULES.map((rule) => ({ ...rule, regex: compile(rule.pattern) }));
const PREPOSITION_REGEX = new RegExp(`${START}(?:${PREPOSITION})${END}(?=\\s+\\S)`, 'giu');
const FILLER_REGEX = compile(FILLER.join('|'));

const overlaps = (taken: [number, number][], [start, end]: [number, number]) => taken.some(([s, e]) => start < e && end > s);

const tidy = (text: string) => text.replace(/\s+/g, ' ').replace(/^[\s,.;:/-]+|[\s,.;:/-]+$/g, '');

export function parseSearch(input: string): ParsedSearch {
  const out: ParsedSearch = { connectors: [], fast: false, openNow: false, nearMe: false, text: '', placeHint: false, tokens: [] };
  const taken: [number, number][] = [];

  for (const rule of COMPILED) {
    for (const match of input.matchAll(rule.regex)) {
      const range: [number, number] = [match.index, match.index + match[0].length];
      if (overlaps(taken, range)) continue;
      taken.push(range);
      rule.apply(match as RegExpExecArray, out, range);
    }
  }

  // "near Bopal" / "in Gandhinagar": the preposition goes, the place stays in the text.
  const prepositions: [number, number][] = [];
  for (const match of input.matchAll(PREPOSITION_REGEX)) {
    const range: [number, number] = [match.index, match.index + match[0].length];
    if (!overlaps(taken, range)) prepositions.push(range);
  }
  taken.push(...prepositions);

  for (const match of input.matchAll(FILLER_REGEX)) {
    const range: [number, number] = [match.index, match.index + match[0].length];
    if (!overlaps(taken, range)) taken.push(range);
  }

  // Whatever nobody claimed is the text.
  const leftover: [number, number][] = [];
  let cursor = 0;
  for (const [start, end] of [...taken].sort((a, b) => a[0] - b[0])) {
    if (start > cursor) leftover.push([cursor, start]);
    cursor = Math.max(cursor, end);
  }
  if (cursor < input.length) leftover.push([cursor, input.length]);
  out.text = tidy(leftover.map(([s, e]) => input.slice(s, e)).join(' '));

  if (prepositions.length > 0 && out.text) {
    out.placeHint = true;
    out.tokens.push({ kind: 'place', label: out.text, ranges: [...prepositions, ...leftover] });
  }
  out.tokens.sort((a, b) => a.ranges[0][0] - b.ranges[0][0]);
  return out;
}

/** The typed text with one understood token taken out (the ✕ on an "Understood" chip). */
export function removeToken(input: string, token: SearchToken): string {
  let result = '';
  let cursor = 0;
  for (const [start, end] of [...token.ranges].sort((a, b) => a[0] - b[0])) {
    result += `${input.slice(cursor, start)} `; // the space keeps neighbouring words apart
    cursor = Math.max(cursor, end);
  }
  return tidy(result + input.slice(cursor));
}
