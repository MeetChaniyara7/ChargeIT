import { CONNECTOR_LABELS } from '@chargespot/shared';
import type { ConnectorType } from '@chargespot/shared';
import type { ReactNode } from 'react';
import { cx } from './cx';

// Stylised plug faces, not technical drawings: each type has its own outline and pin
// pattern so drivers can recognise their plug at a glance. All use currentColor.
const PIN = 1.6;

const FACES: Record<ConnectorType, ReactNode> = {
  // Round Type 2 shell with a flat top, plus two big DC pins below (the "combo" part).
  CCS2: (
    <>
      <path d="M5 4h14l2 5.5a8 8 0 0 1-3 6.5H6a8 8 0 0 1-3-6.5z" />
      <circle cx="8" cy="8.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="8.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="16" cy="8.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="9" cy="12.5" r={PIN} fill="currentColor" stroke="none" />
      <circle cx="15" cy="12.5" r={PIN} fill="currentColor" stroke="none" />
      <circle cx="8" cy="19" r="2" />
      <circle cx="16" cy="19" r="2" />
    </>
  ),
  // Round shell with a flat top and seven small pins.
  TYPE2: (
    <>
      <path d="M5 3.5h14l2 6a9 9 0 1 1-18 0z" />
      <circle cx="8.5" cy="9" r="1" fill="currentColor" stroke="none" />
      <circle cx="15.5" cy="9" r="1" fill="currentColor" stroke="none" />
      <circle cx="7" cy="13" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="13" r="1" fill="currentColor" stroke="none" />
      <circle cx="17" cy="13" r="1" fill="currentColor" stroke="none" />
      <circle cx="9.5" cy="17" r="1" fill="currentColor" stroke="none" />
      <circle cx="14.5" cy="17" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  // Large round plug with two big pins and a row of small ones.
  CHADEMO: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <circle cx="8.5" cy="9" r="2" fill="currentColor" stroke="none" />
      <circle cx="15.5" cy="9" r="2" fill="currentColor" stroke="none" />
      <circle cx="7" cy="15" r="1" fill="currentColor" stroke="none" />
      <circle cx="10.5" cy="16.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="13.5" cy="16.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="17" cy="15" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  // Bharat AC-001: three round pins.
  BHARAT_AC001: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="8" cy="9" r="2" fill="currentColor" stroke="none" />
      <circle cx="16" cy="9" r="2" fill="currentColor" stroke="none" />
      <circle cx="12" cy="16" r="2" fill="currentColor" stroke="none" />
    </>
  ),
  // Bharat DC-001 (GB/T): round shell with a key notch and a ring of pins.
  BHARAT_DC001: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M10 2.5v3h4v-3" />
      <circle cx="8" cy="10" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="16" cy="10" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="12" cy="13" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="8" cy="16.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="16" cy="16.5" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  // Type 1 (J1772): round shell with a flat bottom and five pins.
  TYPE1: (
    <>
      <path d="M12 2.5a9.5 9.5 0 0 1 8 14.5H4A9.5 9.5 0 0 1 12 2.5z" />
      <circle cx="8.5" cy="9" r="1" fill="currentColor" stroke="none" />
      <circle cx="15.5" cy="9" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="8" cy="14" r="1" fill="currentColor" stroke="none" />
      <circle cx="16" cy="14" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  // Anything else: a plain plug.
  OTHER: (
    <>
      <path d="M9 3v5M15 3v5" />
      <path d="M6 8h12v4a6 6 0 0 1-12 0z" />
      <path d="M12 18v3" />
    </>
  ),
};

export interface ConnectorIconProps {
  type: ConnectorType | string;
  /** Show the connector's name next to the icon (recommended; the icon alone is decorative). */
  showLabel?: boolean;
  className?: string;
}

/** A plug icon for a connector type, with the standard label from CONNECTOR_LABELS. */
export function ConnectorIcon({ type, showLabel = true, className }: ConnectorIconProps) {
  const known = type in FACES;
  const face = FACES[(known ? type : 'OTHER') as ConnectorType];
  const label = known ? CONNECTOR_LABELS[type as ConnectorType] : type;

  return (
    <span className={cx('inline-flex items-center gap-1.5', className)}>
      <svg
        viewBox="0 0 24 24"
        className="size-5 shrink-0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        role={showLabel ? undefined : 'img'}
        aria-hidden={showLabel ? true : undefined}
        aria-label={showLabel ? undefined : label}
      >
        {face}
      </svg>
      {showLabel && <span>{label}</span>}
    </span>
  );
}
