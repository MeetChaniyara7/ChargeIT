import type { ReactNode } from 'react';

// Four simple line illustrations for the "How it works" strip. They are decorative
// (the step text beside them says everything), so they are hidden from screen readers.

function Frame({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 64 64" className="size-16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

/** Step 1, Find: a map pin over a map fold. */
export function FindIllustration() {
  return (
    <Frame>
      <path className="text-muted" d="M6 18l14-6 16 6 14-6v34l-14 6-16-6-14 6z" />
      <path className="text-muted" d="M20 12v34M36 18v34" opacity="0.5" />
      <path className="text-primary" d="M44 8a8 8 0 0 1 8 8c0 7-8 14-8 14s-8-7-8-14a8 8 0 0 1 8-8z" fill="currentColor" fillOpacity="0.15" />
      <circle className="text-primary" cx="44" cy="16" r="2.5" fill="currentColor" />
    </Frame>
  );
}

/** Step 2, Book: a calendar with a few blocks selected. */
export function BookIllustration() {
  return (
    <Frame>
      <rect className="text-muted" x="8" y="12" width="48" height="44" rx="6" />
      <path className="text-muted" d="M8 24h48M20 8v8M44 8v8" />
      <rect className="text-primary" x="16" y="32" width="10" height="8" rx="2" fill="currentColor" fillOpacity="0.25" />
      <rect className="text-primary" x="28" y="32" width="10" height="8" rx="2" fill="currentColor" fillOpacity="0.25" />
      <rect className="text-muted" x="40" y="32" width="8" height="8" rx="2" opacity="0.5" />
      <rect className="text-muted" x="16" y="44" width="10" height="6" rx="2" opacity="0.5" />
    </Frame>
  );
}

/** Step 3, Enter code: a number pad with a six-digit code. */
export function CodeIllustration() {
  return (
    <Frame>
      <rect className="text-muted" x="12" y="6" width="40" height="52" rx="6" />
      <g className="text-primary" fill="currentColor" stroke="none">
        <circle cx="19" cy="17" r="2" />
        <circle cx="25" cy="17" r="2" />
        <circle cx="31" cy="17" r="2" />
        <circle cx="37" cy="17" r="2" />
        <circle cx="43" cy="17" r="2" opacity="0.35" />
      </g>
      <g className="text-muted" fill="currentColor" stroke="none">
        {[24, 32, 40].flatMap((x) => [28, 37, 46].map((y) => <circle key={`${x}-${y}`} cx={x} cy={y} r="2.2" />))}
      </g>
    </Frame>
  );
}

/** Step 4, Charge: a battery filling up with a bolt. */
export function ChargeIllustration() {
  return (
    <Frame>
      <rect className="text-muted" x="6" y="20" width="46" height="26" rx="5" />
      <path className="text-muted" d="M56 28v10" />
      <rect className="text-primary" x="11" y="25" width="26" height="16" rx="2.5" fill="currentColor" fillOpacity="0.25" stroke="none" />
      <path className="text-primary" d="M31 22l-8 12h7l-3 9 10-13h-7z" fill="currentColor" />
    </Frame>
  );
}
