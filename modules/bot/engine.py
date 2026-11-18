# modules/bot/engine.py
"""Bot behaviour engine: event queue, priorities, moods and sleep hours.

The engine is deliberately independent of Flask and the LED hardware. A
renderer feeds it a timestamp every frame; tests feed it synthetic events.
"""
import time

from .bus import BotBus
from .face import FaceModel
from .reactions import Reaction, build_reaction
from .schedule import is_sleeping, parse_bool

DEFAULT_WAKE_PRIORITY = 7


class BotEngine:
    def __init__(self, settings=None, bus=None, seed=7, animations=True,
                 now=None):
        self.settings = dict(settings or {})
        self.bus = bus if bus is not None else BotBus()
        self.model = FaceModel(seed=seed, animations=animations)

        self._queue = []
        self._active = None
        self._active_expires = None
        self._last_event = None
        self._manual_sleep = None  # None = follow the schedule, else True/False
        self._sleeping = False
        self._now = float(now or 0.0)
        self._next_poll = 0.0
        self._recent = {}

        self.poll_interval = 0.25
        self.coalesce_window = 1.0
        self.max_queue = 32
        self.event_max_age = 300.0

        self._apply_settings(self.settings)
        if now is not None:
            self.update(now)

    # --- settings ---------------------------------------------------------
    def _apply_settings(self, settings):
        self.settings.update(settings or {})
        self.sleep_enabled = parse_bool(self.settings.get("botSleepEnabled"), False)
        self.sleep_start = self.settings.get("botSleepStart", "22:00")
        self.sleep_end = self.settings.get("botSleepEnd", "07:00")
        self.timezone = self.settings.get("timezone", "UTC") or "UTC"
        self.wake_on_alarm = parse_bool(self.settings.get("botWakeOnAlarm"), True)
        try:
            self.wake_priority = int(
                self.settings.get("botWakePriority", DEFAULT_WAKE_PRIORITY)
            )
        except (TypeError, ValueError):
            self.wake_priority = DEFAULT_WAKE_PRIORITY

    def apply_settings(self, settings):
        self._apply_settings(settings)

    @property
    def active(self):
        return self._active

    @property
    def sleeping(self):
        return self._sleeping

    # --- event handling ---------------------------------------------------
    def handle_event(self, event, now=None):
        """Map one event into the queue. Returns the Reaction or None."""
        now = time.time() if now is None else float(now)
        reaction = build_reaction(event, now)
        if reaction is None:
            return None

        self._last_event = dict(event) if isinstance(event, dict) else None

        if reaction.event_type in ("sleep", "wake"):
            self._manual_sleep = None if parse_bool(event.get("auto"), False) else (
                reaction.event_type == "sleep"
            )
            self._queue.clear()
            self._active = None
            self._active_expires = None
            self._recent.clear()
            return reaction

        if self._is_duplicate(reaction, now):
            return reaction

        if self._active is None:
            self._activate(reaction, now)
        elif reaction.key == self._active.key:
            if reaction.priority >= self._active.priority:
                self._activate(reaction, now)
            else:
                self._enqueue(reaction)
        elif reaction.priority > self._active.priority:
            if not self._expired(self._active, now):
                self._queue.append(self._active)
            self._activate(reaction, now)
        else:
            self._enqueue(reaction)

        return reaction

    def _is_duplicate(self, reaction, now):
        previous = self._recent.get(reaction.key)
        if previous is not None:
            last_time, last_priority = previous
            if now - last_time < self.coalesce_window and reaction.priority <= last_priority:
                return True

        self._recent[reaction.key] = (now, reaction.priority)
        if len(self._recent) > 64:
            cutoff = now - 30.0
            self._recent = {
                key: value for key, value in self._recent.items() if value[0] >= cutoff
            }
        return False

    def _enqueue(self, reaction):
        for index, queued in enumerate(self._queue):
            if queued.key == reaction.key:
                if reaction.priority >= queued.priority:
                    self._queue[index] = reaction
                return
        self._queue.append(reaction)
        if len(self._queue) > self.max_queue:
            self._queue.sort(key=lambda item: (item.priority, item.received_at))
            self._queue.pop(0)

    def _activate(self, reaction, now):
        self._active = reaction
        self._active_expires = (
            now + reaction.duration if reaction.duration > 0 else None
        )

    def _expired(self, reaction, now):
        return (
            reaction is not None
            and reaction.duration > 0
            and now >= self._active_expires
        )

    def _expire(self, now):
        if self._active is None:
            return
        if self._active_expires is not None and now >= self._active_expires:
            self._active = None
            self._active_expires = None

    def _promote(self, now):
        if self._active is not None or not self._queue:
            return
        best = max(
            self._queue, key=lambda item: (item.priority, item.received_at)
        )
        self._queue.remove(best)
        self._activate(best, now)

    # --- frame update -----------------------------------------------------
    def _poll_bus(self, now):
        if now < self._next_poll:
            return
        self._next_poll = now + self.poll_interval
        for event in self.bus.drain(max_age=self.event_max_age, now=now):
            self.handle_event(event, now)

    def update(self, now):
        """Advance the engine to ``now`` and refresh ``self.model``."""
        now = float(now)
        self._now = now

        self._poll_bus(now)
        self._expire(now)
        self._promote(now)

        auto_sleep = is_sleeping(
            now,
            start=self.sleep_start,
            end=self.sleep_end,
            timezone=self.timezone,
            enabled=self.sleep_enabled,
        )
        sleeping = auto_sleep if self._manual_sleep is None else self._manual_sleep

        if (
            sleeping
            and self._active is not None
            and self.wake_on_alarm
            and self._active.priority >= self.wake_priority
        ):
            sleeping = False

        if sleeping != self._sleeping:
            self._sleeping = sleeping
            self.model.set_sleeping(sleeping)

        if not sleeping:
            mood = self._active.mood if self._active is not None else "idle"
            if self.model.mood != mood:
                self.model.set_mood(mood)

        self.model.update(now)

    def state(self):
        active = None
        if self._active is not None:
            active = self._active.as_dict()
            if self._active_expires is not None:
                active["expiresIn"] = max(0.0, self._active_expires - self._now)
        return {
            "mood": self.model.mood,
            "sleeping": self._sleeping,
            "active": active,
            "queued": len(self._queue),
            "lastEvent": self._last_event,
            "now": self._now,
        }

    def feed(self, event, now=None):
        """Convenience alias used by tests and direct integrations."""
        return self.handle_event(event, now=now)
