import type { components } from '@chargespot/shared';

export type LiveSession = components['schemas']['LiveSession'];
export type SimulateResult = components['schemas']['SimulateResult'];
export type EnergyOrder = components['schemas']['EnergyOrderOut'];
export type SessionReceipt = components['schemas']['ReceiptOut'];

/** Why a session ended, in words a driver understands. */
export const END_REASONS: Record<string, string> = {
  USER_STOP: 'You stopped charging.',
  SLOT_END_AUTO_STOP: 'Charging stopped automatically at the end of your booked time.',
  NEXT_BOOKING_AUTO_STOP: 'Charging stopped to leave the charger free for the next booking.',
  PREPAID_USED: 'Charging stopped because your prepaid amount was used up.',
  UNPLUGGED: 'The charger was unplugged.',
  ADMIN: 'Charging stopped because of a problem with the charger.',
};
