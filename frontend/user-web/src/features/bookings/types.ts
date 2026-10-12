import type { components } from '@chargespot/shared';

// Shapes generated from the API (frontend/shared/src/api-types.ts).
type Schemas = components['schemas'];
export type BookingOut = Schemas['BookingOut'];
export type InstantBookingOut = Schemas['InstantBookingOut'];
export type OtpOut = Schemas['OtpOut'];
export type RefundPreview = Schemas['RefundPreview'];
export type Alternatives = Schemas['Alternatives'];
export type DuesOut = Schemas['DuesOut'];
export type OrderOut = Schemas['OrderOut'];
export type VerifyOut = Schemas['VerifyOut'];
export type VerifyRequest = Schemas['VerifyRequest'];
export type VehicleOut = Schemas['VehicleOut'];
export type VehicleIn = Schemas['VehicleIn'];

export type BookingScope = 'upcoming' | 'past';

/** The code is passed to the ticket page in the router's history state, once, and then cleared. */
export interface TicketState {
  otp?: string;
}
