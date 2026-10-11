from pydantic import BaseModel


class Place(BaseModel):
    name: str  # e.g. "Bopal, Ahmedabad, Gujarat, India"
    lat: float
    lng: float
    # The area to show for this place, in Nominatim's order: (south, north, west, east).
    # Present when OpenStreetMap knows it.
    bbox: tuple[float, float, float, float] | None = None
    kind: str | None = None  # e.g. "suburb", "city"


class GeocodeResponse(BaseModel):
    query: str
    places: list[Place]
    cached: bool  # True when answered from our own saved copy
