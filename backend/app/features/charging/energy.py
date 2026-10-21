"""How much energy a charging session delivers, what it costs, and the battery level.

Pure functions. The very same formula is in the database as `session_energy_kwh` (migration 011),
which the background jobs use; a test makes sure the two always give the same answer.

    energy = charger power x hours x efficiency,
             but never more than the battery has room for: battery size x (100% - start level)
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.config import CHARGING_RULES
from app.core.slots import as_utc

KWH = Decimal("0.001")
RUPEE = Decimal("0.01")


def _dec(value) -> Decimal:
    return Decimal(str(value))


def energy_kwh(
    power_kw, started_at: datetime, until: datetime, battery_kwh=None, start_soc_percent=None
) -> Decimal:
    """kWh delivered between `started_at` and `until`, to 3 decimals.

    A charger whose power is unknown delivers nothing we can count. Without a vehicle the default
    battery size is used, and without a known start level the session is assumed to start at 20%.
    """
    elapsed = as_utc(until) - as_utc(started_at)
    seconds = max(Decimal(elapsed.days * 86400 + elapsed.seconds) + Decimal(elapsed.microseconds) / Decimal(10**6), Decimal(0))
    # Multiply first and divide once at the end, in the same order as the SQL function.
    delivered = _dec(power_kw or 0) * seconds * _dec(CHARGING_RULES.efficiency) / Decimal(3600)
    battery = _dec(battery_kwh if battery_kwh is not None else CHARGING_RULES.default_battery_kwh)
    soc = _dec(start_soc_percent if start_soc_percent is not None else CHARGING_RULES.default_start_soc_percent)
    room = battery * (Decimal(100) - soc) / Decimal(100)
    return min(delivered, room).quantize(KWH, rounding=ROUND_HALF_UP)


def bill_amount(energy: Decimal | float, price_per_kwh) -> Decimal:
    """Energy x the charger's price per kWh, in rupees to 2 decimals (an unknown price counts as 0)."""
    return (_dec(energy) * _dec(price_per_kwh or 0)).quantize(RUPEE, rounding=ROUND_HALF_UP)


def battery_percent(energy: Decimal | float, battery_kwh=None, start_soc_percent=None) -> float:
    """The battery level after `energy` kWh went in, from the start level, never above 100."""
    battery = _dec(battery_kwh if battery_kwh is not None else CHARGING_RULES.default_battery_kwh)
    soc = _dec(start_soc_percent if start_soc_percent is not None else CHARGING_RULES.default_start_soc_percent)
    level = soc + _dec(energy) / battery * Decimal(100)
    return float(min(level, Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
