import type { components } from '@chargespot/shared';

type Schemas = components['schemas'];
export type Overview = Schemas['OverviewOut'];
export type Report = Schemas['ReportOut'];
export type StationRow = Schemas['StationRow'];
export type StationRows = Schemas['StationRows'];
export type AdminStation = Schemas['AdminStation'];
export type AdminCharger = Schemas['AdminCharger'];
export type Operator = Schemas['OperatorRow'];
export type UserRow = Schemas['UserRow'];
export type UserRows = Schemas['UserRows'];
export type PaymentRow = Schemas['PaymentRow'];
export type PaymentRows = Schemas['PaymentRows'];
export type ActivityRow = Schemas['ActivityRow'];
export type ActivityRows = Schemas['ActivityRows'];
export type Affected = Schemas['AffectedOut'];
export type OutOfServiceResult = Schemas['OutOfServiceResult'];
export type ChargerEvent = Schemas['ChargerEventOut'];
export type BookingRow = Schemas['BookingRow'];
export type BookingRows = Schemas['BookingRows'];
export type BookingEvent = Schemas['BookingEventOut'];
export type DeviceRow = Schemas['DeviceRow'];
export type DeviceCreated = Schemas['DeviceCreated'];
export type Alert = Schemas['AlertOut'];
export type SimulateResult = Schemas['SimulateResult'];

export const BOOKING_STATUS_OPTIONS = ['HELD', 'CONFIRMED', 'ACTIVE', 'COMPLETED', 'EXPIRED', 'CANCELLED', 'NO_SHOW'] as const;

export const STATUS_LABELS: Record<string, string> = {
  HELD: 'Held',
  CONFIRMED: 'Confirmed',
  ACTIVE: 'Charging',
  COMPLETED: 'Completed',
  EXPIRED: 'Expired',
  CANCELLED: 'Cancelled',
  NO_SHOW: 'No-show',
};
