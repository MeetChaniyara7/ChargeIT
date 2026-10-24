// Checks for the admin forms. Pure, so they have unit tests. The server checks everything again: this only saves a round trip
// and puts the message next to the field.

export interface StationValues {
  name: string;
  address: string;
  city: string;
  latitude: string;
  longitude: string;
  operatorId: string;
  openingHours: string;
}

export type Errors<T> = Partial<Record<keyof T, string>>;

function number(text: string): number | null {
  if (text.trim() === '') return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

export function validateStation(v: StationValues): Errors<StationValues> {
  const errors: Errors<StationValues> = {};
  if (!v.name.trim()) errors.name = 'Enter the station name.';
  else if (v.name.trim().length > 160) errors.name = 'Use at most 160 characters.';
  const lat = number(v.latitude);
  if (lat === null) errors.latitude = 'Enter the latitude as a number, for example 23.0225.';
  else if (lat < -90 || lat > 90) errors.latitude = 'Latitude is between -90 and 90.';
  const lng = number(v.longitude);
  if (lng === null) errors.longitude = 'Enter the longitude as a number, for example 72.5714.';
  else if (lng < -180 || lng > 180) errors.longitude = 'Longitude is between -180 and 180.';
  if (v.address.length > 300) errors.address = 'Use at most 300 characters.';
  if (v.city.length > 120) errors.city = 'Use at most 120 characters.';
  if (v.openingHours.length > 300) errors.openingHours = 'Use at most 300 characters.';
  return errors;
}

export interface ChargerValues {
  label: string;
  connectorType: string;
  currentType: string;
  powerKw: string;
  pricePerKwh: string;
}

export function validateCharger(v: ChargerValues): Errors<ChargerValues> {
  const errors: Errors<ChargerValues> = {};
  if (!v.label.trim()) errors.label = 'Enter a label, for example CCS2-1.';
  else if (v.label.trim().length > 40) errors.label = 'Use at most 40 characters.';
  if (!v.connectorType) errors.connectorType = 'Choose the plug type.';
  if (v.powerKw.trim() !== '') {
    const kw = number(v.powerKw);
    if (kw === null || kw <= 0 || kw > 1000) errors.powerKw = 'Power is a number above 0 and up to 1000 kW. Leave it empty if unknown.';
  }
  if (v.pricePerKwh.trim() !== '') {
    const price = number(v.pricePerKwh);
    if (price === null || price < 0 || price > 1000) errors.pricePerKwh = 'Price is a number from 0 to 1000 rupees per kWh. Leave it empty if unknown.';
  }
  return errors;
}

/** Empty text means "unknown": send null, never an invented zero. */
export function optionalNumber(text: string): number | null {
  return text.trim() === '' ? null : Number(text);
}
