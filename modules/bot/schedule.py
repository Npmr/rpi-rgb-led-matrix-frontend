# modules/bot/schedule.py
"""Sleep-hours handling for the display bot."""
from datetime import datetime
from zoneinfo import ZoneInfo


def parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "on", "yes", "enabled")


def parse_clock(value, default="22:00"):
    """Return a ``HH:MM`` string as minutes since midnight."""
    text = str(value or "").strip()
    fallback = str(default)
    if not text:
        text = fallback
    try:
        hours_text, minutes_text = text.split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except (ValueError, AttributeError):
        if text != fallback:
            return parse_clock(fallback, "00:00")
        return 0
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        if text != fallback:
            return parse_clock(fallback, "00:00")
        return 0
    return hours * 60 + minutes


def is_sleeping(now, start="22:00", end="07:00", timezone="UTC", enabled=True):
    """Return True when the local time is inside the sleep window.

    Windows may wrap around midnight (22:00 - 07:00). An empty window
    (start == end) is treated as disabled instead of a full day.
    """
    if not parse_bool(enabled, False):
        return False

    start_minutes = parse_clock(start, "22:00")
    end_minutes = parse_clock(end, "07:00")
    if start_minutes == end_minutes:
        return False

    try:
        zone = ZoneInfo(str(timezone or "UTC"))
    except Exception:
        zone = ZoneInfo("UTC")

    local = datetime.fromtimestamp(float(now), zone)
    current = local.hour * 60 + local.minute

    if start_minutes < end_minutes:
        return start_minutes <= current < end_minutes
    return current >= start_minutes or current < end_minutes
