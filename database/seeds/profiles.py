"""Realistic charger setups per operator, used to fill gaps in real data.

Public data for India rarely includes prices and often leaves out power or connector
details. Instead of leaving stations unbookable, we generate plausible values based on
what each operator typically installs. Everything generated here is tagged as
synthetic (or listed in estimated_fields), and the app shows an "approximate data" badge.

Generation is deterministic: the random choices are seeded by the station's ID, so
running the seed again produces exactly the same chargers and prices.
"""

import random
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class PlugOption:
    connector_type: str
    power_choices_kw: tuple[float, ...]
    price_range_inr: tuple[float, float]      # ₹ per kWh, inclusive of GST


DC_CCS2_FAST = PlugOption("CCS2", (30, 50, 60), (18, 22))
DC_CCS2_RAPID = PlugOption("CCS2", (60, 120), (21, 25))
DC_BHARAT = PlugOption("BHARAT_DC001", (15,), (15, 18))
AC_TYPE2 = PlugOption("TYPE2", (7.4, 11, 22), (12, 16))
AC_BHARAT = PlugOption("BHARAT_AC001", (3.3,), (10, 13))
DC_CHADEMO = PlugOption("CHADEMO", (25, 50), (18, 22))

# Operator -> (always-present plugs, optional extra plugs). Plugs are chosen per station.
OPERATOR_PROFILES: dict[str, tuple[tuple[PlugOption, ...], tuple[PlugOption, ...]]] = {
    "Tata Power": ((DC_CCS2_FAST,), (DC_CCS2_FAST, AC_TYPE2)),
    "Jio-bp": ((DC_CCS2_RAPID,), (DC_CCS2_RAPID, AC_TYPE2)),
    "ChargeZone": ((DC_CCS2_RAPID,), (DC_CCS2_FAST, DC_CCS2_RAPID)),
    "Statiq": ((DC_CCS2_FAST,), (AC_TYPE2, DC_CCS2_FAST)),
    "Torrent Power": ((DC_CCS2_FAST,), (AC_TYPE2,)),
    "Indian Oil (IOCL)": ((DC_CCS2_FAST,), (DC_BHARAT,)),
    "Hindustan Petroleum (HPCL)": ((DC_CCS2_FAST,), (DC_BHARAT,)),
    "Bharat Petroleum (BPCL)": ((DC_CCS2_FAST,), (DC_BHARAT,)),
    "CESL": ((DC_BHARAT,), (DC_CCS2_FAST, AC_BHARAT)),
    "EESL": ((DC_BHARAT,), (AC_BHARAT, DC_CCS2_FAST)),
    "Shell Recharge": ((DC_CCS2_RAPID,), (DC_CCS2_FAST,)),
    "GLIDA (Fortum)": ((DC_CCS2_FAST,), (DC_CHADEMO, AC_TYPE2)),
}
# Unknown operators: usually a hotel, mall or small business with an AC charger,
# sometimes with one fast DC charger.
DEFAULT_PROFILE = ((AC_TYPE2,), (DC_CCS2_FAST, AC_TYPE2))


def rng_for(station_id: str, salt: str = "") -> random.Random:
    """A random generator that always gives the same sequence for the same station."""
    return random.Random(uuid.UUID(str(station_id)).int ^ hash_text(salt))


def hash_text(text: str) -> int:
    # Python's built-in hash() changes between runs; this one is stable.
    value = 0
    for ch in text:
        value = (value * 131 + ord(ch)) % (2**61 - 1)
    return value


def pick_price(rng: random.Random, plug: PlugOption) -> float:
    low, high = plug.price_range_inr
    return round(rng.uniform(low, high) * 2) / 2   # nearest 50 paise, like real tariffs


def generate_chargers(station_id: str, operator: str | None, count: int | None = None) -> list[dict]:
    """Synthetic chargers for a station: [{'connector_type', 'power_kw', 'price_per_kwh'}]."""
    rng = rng_for(station_id, "chargers")
    always, extras = OPERATOR_PROFILES.get(operator or "", DEFAULT_PROFILE)
    if count is None:
        count = len(always) + rng.choice((0, 1, 1, 2))
    plugs = list(always) + [rng.choice(extras) for _ in range(max(0, count - len(always)))]
    return [
        {
            "connector_type": plug.connector_type,
            "power_kw": float(rng.choice(plug.power_choices_kw)),
            "price_per_kwh": pick_price(rng, plug),
        }
        for plug in plugs[:count]
    ]


def estimate_power(station_id: str, label: str, connector_type: str) -> float:
    rng = rng_for(station_id, "power:" + label)
    options = {
        "CCS2": DC_CCS2_FAST, "CHADEMO": DC_CHADEMO, "BHARAT_DC001": DC_BHARAT,
        "TYPE2": AC_TYPE2, "BHARAT_AC001": AC_BHARAT, "TYPE1": AC_TYPE2,
    }.get(connector_type, AC_TYPE2)
    return float(rng.choice(options.power_choices_kw))


def estimate_price(station_id: str, label: str, power_kw: float) -> float:
    """Typical Indian public tariffs: slow AC ~₹10-16, DC ~₹16-22, rapid DC (>60 kW) ~₹21-25."""
    rng = rng_for(station_id, "price:" + label)
    band = (10, 16) if power_kw <= 22 else (16, 22) if power_kw <= 60 else (21, 25)
    return round(rng.uniform(*band) * 2) / 2


def estimate_rating(station_id: str) -> tuple[float, int]:
    rng = rng_for(station_id, "rating")
    return round(rng.uniform(3.6, 4.8), 1), rng.randint(5, 140)
