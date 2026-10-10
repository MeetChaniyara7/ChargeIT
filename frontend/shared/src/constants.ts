// Fixed lists used by the API, the database and both front ends.
// These MUST match the database CHECK constraints in docs/architecture.md section 5.2.
// If you change a list here, change the migration and the API at the same time.

export const SLOT_MINUTES = 30;
export const MIN_BLOCKS_PER_BOOKING = 1;
export const MAX_BLOCKS_PER_BOOKING = 4;
export const DISPLAY_TIME_ZONE = 'Asia/Kolkata';

/** Lifecycle of a booking (see the state diagram in docs/architecture.md section 6.1). */
export const BOOKING_STATUSES = [
  'HELD',
  'CONFIRMED',
  'ACTIVE',
  'COMPLETED',
  'EXPIRED',
  'CANCELLED',
  'NO_SHOW',
] as const;
export type BookingStatus = (typeof BOOKING_STATUSES)[number];

/** Statuses that occupy a charger's time (the no-double-booking constraint applies to these). */
export const LIVE_BOOKING_STATUSES = ['HELD', 'CONFIRMED', 'ACTIVE'] as const satisfies readonly BookingStatus[];

/** APP = booked ahead (₹199 fee), INSTANT = "Charge now" in the app, WALK_IN = kiosk QR. */
export const BOOKING_SOURCES = ['APP', 'INSTANT', 'WALK_IN'] as const;
export type BookingSource = (typeof BOOKING_SOURCES)[number];

/** The charger's live physical state, as reported by the (simulated) charger. */
export const CHARGER_STATUSES = ['AVAILABLE', 'RESERVED', 'CHARGING', 'FAULTED', 'OUT_OF_SERVICE'] as const;
export type ChargerStatus = (typeof CHARGER_STATUSES)[number];

export const CONNECTOR_TYPES = ['CCS2', 'TYPE2', 'CHADEMO', 'BHARAT_AC001', 'BHARAT_DC001', 'TYPE1', 'OTHER'] as const;
export type ConnectorType = (typeof CONNECTOR_TYPES)[number];

export const CONNECTOR_LABELS: Record<ConnectorType, string> = {
  CCS2: 'CCS2',
  TYPE2: 'Type 2',
  CHADEMO: 'CHAdeMO',
  BHARAT_AC001: 'Bharat AC-001',
  BHARAT_DC001: 'Bharat DC-001 (GB/T)',
  TYPE1: 'Type 1',
  OTHER: 'Other',
};

/** BOOKING = started with an OTP, WALK_IN = kiosk QR, EXTERNAL = operator's own app/card. */
export const SESSION_SOURCES = ['BOOKING', 'WALK_IN', 'EXTERNAL'] as const;
export type SessionSource = (typeof SESSION_SOURCES)[number];

export const BILL_STATUSES = ['DUE', 'PAID', 'PREPAID_SETTLED'] as const;
export type BillStatus = (typeof BILL_STATUSES)[number];

/** Where a station's or charger's data came from. 'synthetic' shows an "approximate data" badge. */
export const DATA_SOURCES = ['ocm', 'osm', 'synthetic', 'manual'] as const;
export type DataSource = (typeof DATA_SOURCES)[number];
