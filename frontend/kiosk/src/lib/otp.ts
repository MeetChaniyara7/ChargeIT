// The on-screen code pad: what each button does to the digits typed so far. Pure, so it has unit tests.

export const CODE_LENGTH = 6;

export type PadKey = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | 'delete' | 'clear';

/** Applies one button press. Digits stop at six; delete removes the last; clear empties the pad. */
export function pressKey(code: string, key: PadKey): string {
  if (key === 'clear') return '';
  if (key === 'delete') return code.slice(0, -1);
  return code.length >= CODE_LENGTH ? code : code + key;
}

export function isComplete(code: string): boolean {
  return code.length === CODE_LENGTH;
}

/** What to tell the driver for each way a code can fail. Messages from the server are used for the rest. */
export function otpFailureMessage(error: { code: string; message: string; details?: Record<string, unknown> }): string {
  const left = typeof error.details?.tries_left === 'number' ? error.details.tries_left : null;
  switch (error.code) {
    case 'WRONG_OTP':
      return left === null ? 'Wrong code. Please try again.' : `Wrong code, ${left} ${left === 1 ? 'try' : 'tries'} left`;
    case 'OTP_NOT_VALID_NOW':
      return 'This code is not valid right now. It works from 15 minutes before your slot until 10 minutes after it starts.';
    case 'CHARGER_UNAVAILABLE':
      return 'That charger cannot start right now. Please try another time or ask the station staff.';
    default:
      return error.message;
  }
}
