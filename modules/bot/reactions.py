# modules/bot/reactions.py
"""Translate incoming bot events into facial reactions.

The mapping is intentionally data-driven so MQTT/HA automations can stay short:
``{"type": "meeting_soon"}`` is enough, while every field (mood, priority,
duration, text) can still be overridden by the sender.
"""
import time
from dataclasses import asdict, dataclass

from .face import MOODS

MAX_TEXT = 160
MAX_DURATION = 3600.0
MAX_PRIORITY = 10

# event type -> (mood, priority, duration seconds)
_DEFAULTS = {
    "message": ("curious", 3, 8.0),
    "meeting_soon": ("alarmed", 7, 300.0),
    "meeting_started": ("thinking", 5, 60.0),
    "meeting_ended": ("happy", 5, 8.0),
    "doorbell": ("alarmed", 8, 10.0),
    "timer_done": ("excited", 7, 10.0),
    "news": ("curious", 3, 12.0),
    "alarm": ("alarmed", 9, 30.0),
    "weather": ("curious", 2, 20.0),
    "mood": ("idle", 4, 5.0),
    "sleep": ("sleepy", 0, 0.0),
    "wake": ("idle", 0, 0.0),
}

_DEFAULT_TEXT = {
    "meeting_soon": "Meeting soon",
    "meeting_started": "Meeting started",
    "meeting_ended": "Meeting ended",
    "doorbell": "Someone is at the door",
    "timer_done": "Timer finished",
    "alarm": "Alarm",
}

_ALIASES = {
    "say": "message",
    "notify": "message",
    "text": "message",
    "weather_update": "weather",
    "calendar": "meeting_soon",
}

_WEATHER_MOODS = {
    "clear": "happy",
    "sunny": "happy",
    "partlycloudy": "happy",
    "cloudy": "idle",
    "overcast": "idle",
    "rain": "sad",
    "rainy": "sad",
    "pouring": "sad",
    "drizzle": "sad",
    "showers": "sad",
    "snow": "curious",
    "snowy": "curious",
    "sleet": "sad",
    "storm": "alarmed",
    "stormy": "alarmed",
    "lightning": "alarmed",
    "thunderstorm": "alarmed",
    "fog": "thinking",
    "mist": "thinking",
    "windy": "curious",
    "hot": "sleepy",
    "cold": "sad",
}


@dataclass(frozen=True)
class Reaction:
    event_type: str
    mood: str
    priority: int
    duration: float
    text: str = ""
    key: str = ""
    source: str = "api"
    received_at: float = 0.0

    def as_dict(self):
        return asdict(self)

    @property
    def expires(self):
        return self.duration > 0


def _coerce_priority(value, default):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    return max(0, min(MAX_PRIORITY, number))


def _coerce_duration(value, default):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(MAX_DURATION, number))


def _weather_mood(condition, temperature):
    key = str(condition or "").strip().lower().replace("_", "").replace(" ", "")
    if key in _WEATHER_MOODS:
        return _WEATHER_MOODS[key]

    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = None
    if temperature is not None:
        if temperature >= 30:
            return "sleepy"
        if temperature <= 0:
            return "sad"
    return "curious"


def _text_of(event):
    for key in ("text", "message", "value", "title"):
        value = event.get(key)
        if value is not None:
            return str(value).strip()[:MAX_TEXT]
    return ""


def _event_type_of(event, text):
    raw = event.get("type") or event.get("event")
    if raw is None:
        if event.get("mood"):
            return "mood"
        if event.get("condition") or event.get("weather"):
            return "weather"
        return "message" if text else ""

    event_type = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(event_type, event_type)


def build_reaction(event, now=None):
    """Return a Reaction for ``event`` or None when it carries no instruction."""
    if not isinstance(event, dict):
        return None

    now = time.time() if now is None else float(now)
    text = _text_of(event)
    event_type = _event_type_of(event, text)
    if not event_type:
        return None

    known = event_type in _DEFAULTS
    if not known:
        if text or event.get("mood"):
            event_type = "message" if text else "mood"
        else:
            return None

    mood, priority, duration = _DEFAULTS[event_type]
    if event_type == "weather":
        mood = _weather_mood(
            event.get("condition") or event.get("weather"),
            event.get("temp", event.get("temperature")),
        )
    if event_type == "message" and not text:
        text = _DEFAULT_TEXT.get(event_type, "")

    requested_mood = event.get("mood")
    if isinstance(requested_mood, str) and requested_mood in MOODS:
        mood = requested_mood

    priority = _coerce_priority(event.get("priority"), priority)
    duration = _coerce_duration(event.get("duration"), duration)
    if not text:
        text = _DEFAULT_TEXT.get(event_type, "")

    key = event.get("key")
    if key is None:
        if event_type == "message":
            key = f"message:{text.casefold()}" if text else "message"
        elif event_type == "mood":
            key = f"mood:{mood}"
        else:
            key = event_type
    key = str(key)[:120]

    return Reaction(
        event_type=event_type,
        mood=mood,
        priority=priority,
        duration=duration,
        text=text,
        key=key,
        source=str(event.get("_source") or event.get("source") or "api"),
        received_at=float(event.get("_receivedAt") or now),
    )
