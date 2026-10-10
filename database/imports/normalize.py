"""Cleaning rules for imported station data. Pure functions: no database, no network.

Raw data from OpenStreetMap and Open Charge Map spells the same thing many ways
("tata", "TATA", "Tata Power EZ Charge"; "CCS (Type 2)", "socket:type2_combo"). These
functions turn it into one consistent vocabulary, and decide which records are not
bookable car chargers at all.
"""

import re

# ---------------------------------------------------------------- operators

# Canonical operator name -> words that identify it (checked case-insensitively, as
# whole words or prefixes). Order matters: more specific entries first.
OPERATOR_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    ("Tata Power", ("tata power", "tata ez", "ez charge", "tata")),
    ("Jio-bp", ("jio-bp", "jio bp", "jiobp", "jio pulse", "jio-bp pulse", "bp pulse")),
    ("ChargeZone", ("chargezone", "charge zone")),
    ("Statiq", ("statiq",)),
    ("Ather Grid", ("ather",)),
    ("Ola Hypercharger", ("ola hyper", "ola electric", "ola ")),
    ("Zeon Charging", ("zeon",)),
    ("EESL", ("eesl", "energy efficiency services")),
    ("CESL", ("cesl", "convergence energy")),
    ("Indian Oil (IOCL)", ("iocl", "indian oil", "indianoil")),
    ("Hindustan Petroleum (HPCL)", ("hpcl", "hindustan petroleum", "hp echarge")),
    ("Bharat Petroleum (BPCL)", ("bpcl", "bharat petroleum", "edrive bpcl")),
    ("Shell Recharge", ("shell",)),
    ("Torrent Power", ("torrent",)),
    ("GLIDA (Fortum)", ("glida", "fortum")),
    ("Magenta ChargeGrid", ("magenta",)),
    ("Bolt.Earth", ("bolt.earth", "bolt earth", "bolt")),
    ("Kazam", ("kazam",)),
    ("Electreefi", ("electreefi",)),
    ("GoEgo", ("goego", "go ego")),
    ("PowerGrid", ("powergrid", "power grid")),
    ("Tesla", ("tesla",)),
    ("MobiLane", ("mobilane", "mobi lane")),
]

# Values that mean "we don't know the operator".
UNKNOWN_OPERATORS = {"", "unknown", "(unknown operator)", "unknown operator", "?", "(business owner at location)"}


def _matches(text: str, keyword: str) -> bool:
    """Whole-word match, so 'ola' matches 'Ola Electric' but not 'Olavanna'."""
    return re.search(r"(?<![a-z0-9])" + re.escape(keyword.strip()) + r"(?![a-z0-9])", text) is not None


def _known_operator(text: str) -> str | None:
    for canonical, keywords in OPERATOR_ALIASES:
        if any(_matches(text, k) for k in keywords):
            return canonical
    return None


def normalize_operator(*operator_values: str | None, station_name: str | None = None) -> str | None:
    """Return the canonical operator name.

    operator_values are operator fields from the source, tried in order (e.g. the OSM
    operator, brand and network tags). Unrecognised but real operator names are kept,
    tidied up. The station name is only used to *recognise* a known operator
    ("MobiLane AMC Kankariya" -> MobiLane); it never becomes the operator itself.
    """
    fallback = None
    for raw in operator_values:
        if not raw:
            continue
        text = " ".join(raw.split()).lower()
        if text in UNKNOWN_OPERATORS:
            continue
        known = _known_operator(text)
        if known:
            return known
        if fallback is None:
            fallback = re.sub(r"\s*\((in|india)\)\s*$", "", " ".join(raw.split()), flags=re.I)
    if fallback:
        return fallback
    return _known_operator(" ".join((station_name or "").split()).lower())


# Indian states and union territories, to spot records whose address contradicts their coordinates.
INDIAN_STATES = (
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur",
    "meghalaya", "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana",
    "tripura", "uttar pradesh", "uttarakhand", "west bengal", "delhi", "jammu and kashmir", "ladakh",
    "puducherry", "chandigarh", "dadra and nagar haveli", "daman and diu", "lakshadweep",
)


def names_other_state(region_name: str, *texts: str | None) -> str | None:
    """Return another state named in the address texts, if any (e.g. 'karnataka')."""
    combined = " ".join(t for t in texts if t).lower()
    region = region_name.lower()
    for state in INDIAN_STATES:
        if state != region and _matches(combined, state):
            return state
    return None


# ---------------------------------------------------------------- connectors

DC_CONNECTORS = {"CCS2", "CHADEMO", "BHARAT_DC001"}
AC_CONNECTORS = {"TYPE2", "TYPE1", "BHARAT_AC001"}

# Plugs that only scooters/bikes use. A station with nothing but these is a two-wheeler station.
TWO_WHEELER_PLUG_WORDS = ("type m", "lecct", "ather", "domestic", "type d", "bs 1363", "3 pin socket", "5 pin")


def current_type_for(connector: str) -> str | None:
    if connector in DC_CONNECTORS:
        return "DC"
    if connector in AC_CONNECTORS:
        return "AC"
    return None


def connector_from_title(title: str | None, current: str | None = None) -> str | None:
    """Map an Open Charge Map connection title to our connector type.

    Returns None when the plug is unknown or is a two-wheeler-only plug.
    """
    t = (title or "").lower()
    if not t or t == "unknown" or any(w in t for w in TWO_WHEELER_PLUG_WORDS):
        return None
    if "ccs" in t and ("type 1" in t or "combo 1" in t):
        return "OTHER"           # CCS1 (American); not used in India
    if "ccs" in t or "combo 2" in t or "type 2 combo" in t:
        return "CCS2"
    if "chademo" in t:
        return "CHADEMO"
    if "gb-t" in t or "gb/t" in t or "gbt" in t:
        return "BHARAT_DC001" if (current or "").upper().startswith("DC") else "OTHER"
    if "bharat" in t and "dc" in t:
        return "BHARAT_DC001"
    if "bharat" in t and "ac" in t:
        return "BHARAT_AC001"
    if "60309" in t:
        return "BHARAT_AC001"    # Bharat AC-001 uses the IEC 60309 industrial socket
    if "type 2" in t or "mennekes" in t:
        return "TYPE2"
    if "type 1" in t or "j1772" in t:
        return "TYPE1"
    if "tesla" in t or "nacs" in t:
        return "OTHER"
    return "OTHER"


def is_two_wheeler_plug(title: str | None) -> bool:
    t = (title or "").lower()
    return any(w in t for w in TWO_WHEELER_PLUG_WORDS)


# OpenStreetMap socket tags -> our connector types.
OSM_SOCKETS = {
    "type2_combo": "CCS2",
    "type2": "TYPE2",
    "type2_cable": "TYPE2",
    "chademo": "CHADEMO",
    "type1": "TYPE1",
    "type1_combo": "OTHER",
    "gb_dc": "BHARAT_DC001",
    "gb_ac": "OTHER",
    "bharat_dc001": "BHARAT_DC001",
    "bharat_ac001": "BHARAT_AC001",
    "iec_60309": "BHARAT_AC001",
    "tesla_supercharger": "OTHER",
}


def parse_power_kw(text: str | None) -> float | None:
    """'60 kW' -> 60.0, '7400 W' -> 7.4, '22' -> 22.0 (bare numbers above 500 are watts)."""
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kw|w)?", text.lower())
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    unit = m.group(2)
    if unit == "w" or (unit is None and value > 500):
        value /= 1000
    return round(value, 1) if 0 < value <= 400 else None


def connectors_from_osm_tags(tags: dict[str, str]) -> list[dict]:
    """Read socket:* tags into [{'connector_type', 'count', 'power_kw'}]."""
    result = []
    for key, value in tags.items():
        m = re.fullmatch(r"socket:([a-z0-9_]+)", key)
        if not m or m.group(1) not in OSM_SOCKETS:
            continue
        try:
            count = int(value)
        except ValueError:
            count = 1 if value.lower() in ("yes",) else 0
        if count <= 0:
            continue
        result.append({
            "connector_type": OSM_SOCKETS[m.group(1)],
            "count": min(count, 10),
            "power_kw": parse_power_kw(tags.get(f"{key}:output")),
        })
    return result


# ---------------------------------------------------------------- what counts as a station

# Not charging stations anyone can book: battery swapping, bikes, phones.
EXCLUDE_WORDS = ("swap", "battery smart", "sun mobility", "yulu", "phone charging", "mobile charging",
                 "cycle", "bicycle", "e-rickshaw", "erickshaw")

# Networks that serve only scooters and motorbikes.
TWO_WHEELER_NETWORK_WORDS = ("ather", "ola hyper", "ola electric", "revolt", "hero vida", "vida ", "tvs ",
                             "okinawa", "bounce", "goelectrify", "simple energy", "okaya")


def classify(name: str | None, operator: str | None, plug_titles: list[str] | None = None,
             tags: dict[str, str] | None = None) -> str:
    """Return 'EXCLUDE', 'TWO_WHEELER' or 'FOUR_WHEELER' for one source record."""
    text = f" {name or ''} {operator or ''} ".lower()
    if any(w in text for w in EXCLUDE_WORDS):
        return "EXCLUDE"
    tags = tags or {}
    if tags.get("amenity") == "charging_station" and tags.get("motorcar") == "no":
        if tags.get("bicycle") == "yes" and not any(tags.get(k) == "yes" for k in ("scooter", "motorcycle")):
            return "EXCLUDE"
        return "TWO_WHEELER"
    if any(w in text for w in TWO_WHEELER_NETWORK_WORDS):
        return "TWO_WHEELER"
    known_plugs = [p for p in (plug_titles or []) if p and p.lower() != "unknown"]
    if known_plugs and all(is_two_wheeler_plug(p) for p in known_plugs):
        return "TWO_WHEELER"
    return "FOUR_WHEELER"


# ---------------------------------------------------------------- names and prices

GENERIC_NAME_WORDS = {"ev", "electric", "vehicle", "charging", "charger", "chargers", "station", "point",
                      "hub", "unknown", "fast", "public", "the", "and", "-", "–", "&"}


def is_generic_name(name: str | None) -> bool:
    words = re.findall(r"[a-z0-9]+", (name or "").lower())
    return not words or all(w in GENERIC_NAME_WORDS for w in words)


def clean_station_name(name: str | None, operator: str | None, area: str | None) -> str:
    """Keep real names; replace junk like 'Unknown Charging Station' with '<operator> – <area>'."""
    name = " ".join((name or "").split()).strip(" -–,")
    if not is_generic_name(name):
        return name
    parts = [p for p in (operator, area) if p]
    return " – ".join(parts) if parts else "EV Charging Station"


def parse_price_per_kwh(text: str | None) -> float | None:
    """Read a ₹/kWh price from free text like '21/kWh', 'Rs 14', '21rs', '₹18 per unit'.

    Only believable prices (₹5-₹40 per kWh) are accepted; anything else counts as unknown.
    """
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not m:
        return None
    value = float(m.group(1))
    return value if 5 <= value <= 40 else None
