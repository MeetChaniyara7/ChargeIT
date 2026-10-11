/** Straight-line distance in kilometres between two points (same formula as the server). */
export function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const a =
    Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lng2 - lng1) / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.sqrt(a));
}
