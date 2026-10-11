"""Is a station open right now? Reads the common OpenStreetMap-style opening hours.

Understood:   24/7
              08:00-22:00                    (every day)
              Mo-Fr 09:00-18:00; Sa 10:00-14:00
              Mo-Su 00:00-24:00
              22:00-06:00                    (overnight)
              Mo-Sa 08:00-12:00,14:00-18:00  (two ranges)
              Su off

Anything else (public holidays, sunrise/sunset, ...) returns None, meaning "unknown".
We never guess: the "Open now" filter only hides stations that are KNOWN to be closed.
"""

import re
from datetime import datetime

from app.core.slots import IST, as_utc

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_TIME_RANGE = r"\d{1,2}:\d{2}-\d{1,2}:\d{2}"
_RULE = re.compile(rf"^(?:(?P<days>[A-Za-z, -]+?)\s+)?(?P<times>{_TIME_RANGE}(?:,\s*{_TIME_RANGE})*|off)$")


def _days(spec: str | None) -> set[int] | None:
    """'Mo-Fr' -> {0..4}, 'Sa,Su' -> {5, 6}. None when it can't be read."""
    if not spec:
        return set(range(7))
    result: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        if "-" in part:
            start, _, end = part.partition("-")
            if start not in DAYS or end not in DAYS:
                return None
            i, j = DAYS.index(start), DAYS.index(end)
            result |= set(range(i, j + 1)) if i <= j else set(range(i, 7)) | set(range(0, j + 1))
        elif part in DAYS:
            result.add(DAYS.index(part))
        else:
            return None
    return result


def _minutes(text: str) -> int | None:
    hours, _, minutes = text.partition(":")
    h, m = int(hours), int(minutes)
    return h * 60 + m if (0 <= h <= 24 and 0 <= m < 60 and not (h == 24 and m)) else None


def _within(ranges: str, minute_of_day: int) -> bool | None:
    open_now = False
    for rng in ranges.split(","):
        start_text, _, end_text = rng.strip().partition("-")
        start, end = _minutes(start_text), _minutes(end_text)
        if start is None or end is None:
            return None
        if start <= end:
            open_now |= start <= minute_of_day < end
        else:  # overnight, e.g. 22:00-06:00
            open_now |= minute_of_day >= start or minute_of_day < end
    return open_now


def is_open_now(hours: str | None, now: datetime) -> bool | None:
    """True / False when the hours are understood, None when unknown."""
    if not hours or not hours.strip():
        return None
    text = hours.strip()
    if text == "24/7":
        return True

    local = as_utc(now).astimezone(IST)
    today, minute_of_day = local.weekday(), local.hour * 60 + local.minute
    result: bool | None = False  # days that no rule mentions are closed

    for raw_rule in text.split(";"):
        match = _RULE.match(raw_rule.strip())
        if not match:
            return None
        days = _days(match.group("days"))
        if days is None:
            return None
        if today not in days:
            continue
        times = match.group("times")
        result = False if times == "off" else _within(times, minute_of_day)
        if result is None:
            return None
    return result

