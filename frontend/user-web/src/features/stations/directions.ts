/** A link that opens turn-by-turn directions to a station in Google Maps. */
export const directionsUrl = (station: { latitude: number; longitude: number }): string =>
  `https://www.google.com/maps/dir/?api=1&destination=${station.latitude},${station.longitude}`;
