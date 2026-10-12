// A rough cost of the electricity for a booked time, shown as "Est. charging ₹486".
// Pure function, so the summary bar, the ticket and the tests all agree.
//
// It follows how the simulated charger will behave (docs/architecture.md section 8):
//   energy = charger power x charging time x efficiency, limited by the vehicle's battery.
// It is only an estimate: the real bill is the energy actually delivered x the price per kWh.

/** The share of a charger's rated power that reaches the battery. */
export const CHARGING_EFFICIENCY = 0.9;

export interface EnergyEstimate {
  kwh: number;
  cost: number;
  /** True when the vehicle's battery size, not the booked time, set the limit. */
  limitedByBattery: boolean;
}

export interface EstimateInput {
  powerKw: number | null | undefined;
  pricePerKwh: number | null | undefined;
  minutes: number;
  /** The driver's battery size. Without it the estimate has no battery limit. */
  batteryKwh?: number | null;
}

/** The estimate, or null when the power or price is unknown (we never invent a number). */
export function estimateEnergy({ powerKw, pricePerKwh, minutes, batteryKwh }: EstimateInput): EnergyEstimate | null {
  if (powerKw == null || pricePerKwh == null || !(powerKw > 0) || !(pricePerKwh >= 0) || !(minutes > 0)) return null;
  let kwh = powerKw * (minutes / 60) * CHARGING_EFFICIENCY;
  let limitedByBattery = false;
  if (batteryKwh != null && batteryKwh > 0 && kwh > batteryKwh) {
    kwh = batteryKwh;
    limitedByBattery = true;
  }
  return { kwh, cost: Math.round(kwh * pricePerKwh * 100) / 100, limitedByBattery };
}
