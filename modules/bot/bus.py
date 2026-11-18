# modules/bot/bus.py
"""Cross-process event spool for the display bot.

The Flask process receives events (REST/MQTT) while the renderer is a separate
process that owns the LED matrix. A small directory of one-JSON-file events is
the simplest robust bridge: writes are atomic, no locks are shared, and a
renderer restart cannot deadlock the web UI.

Events older than ``max_age`` seconds are dropped instead of replayed, so a
reminder does not suddenly appear hours later.
"""
import json
import os
import time
import uuid

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_EVENTS_DIR = os.path.join(PROJECT_ROOT, "runtime", "bot", "events")
DEFAULT_MAX_AGE = 300.0
DEFAULT_MAX_EVENTS = 128


def default_events_dir():
    return os.environ.get("BOT_EVENTS_DIR", DEFAULT_EVENTS_DIR)


class BotBus:
    """A tiny durable queue of bot events."""

    def __init__(self, directory=None, max_age=DEFAULT_MAX_AGE,
                 max_events=DEFAULT_MAX_EVENTS):
        self.directory = directory or default_events_dir()
        self.max_age = float(max_age)
        self.max_events = max(1, int(max_events))

    def ensure_directory(self):
        os.makedirs(self.directory, exist_ok=True)

    def publish(self, event, source="api", now=None):
        """Store ``event`` atomically and return the stored dictionary."""
        if not isinstance(event, dict):
            raise TypeError("bot events must be dictionaries")

        now = time.time() if now is None else float(now)
        stored = dict(event)
        stored.setdefault("type", "message")
        stored["_id"] = uuid.uuid4().hex
        stored["_receivedAt"] = now
        stored["_source"] = str(source or "api")

        self.ensure_directory()
        name = f"{int(now * 1_000_000_000):020d}-{stored['_id']}.json"
        final_path = os.path.join(self.directory, name)
        temporary_path = os.path.join(self.directory, f".{name}.tmp")

        try:
            with open(temporary_path, "w", encoding="utf-8") as handle:
                json.dump(stored, handle, separators=(",", ":"), ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, final_path)
        except OSError:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise

        self.prune(now=now)
        return stored

    def drain(self, max_age=None, now=None):
        """Return all pending events (oldest first) and remove their files."""
        now = time.time() if now is None else float(now)
        if max_age is None:
            max_age = self.max_age

        try:
            names = sorted(os.listdir(self.directory))
        except OSError:
            return []

        events = []
        for name in names:
            if not name.endswith(".json") or name.startswith("."):
                continue
            path = os.path.join(self.directory, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                data = None

            try:
                os.unlink(path)
            except OSError:
                pass

            if not isinstance(data, dict):
                continue
            received = data.get("_receivedAt")
            if isinstance(received, (int, float)) and now - received > max_age:
                continue
            events.append(data)

        return events

    def prune(self, now=None):
        """Drop stale and excess event files."""
        now = time.time() if now is None else float(now)
        try:
            names = sorted(
                name for name in os.listdir(self.directory)
                if name.endswith(".json") and not name.startswith(".")
            )
        except OSError:
            return

        overflow = max(0, len(names) - self.max_events)
        for name in names[:overflow]:
            try:
                os.unlink(os.path.join(self.directory, name))
            except OSError:
                pass

        for name in names[overflow:]:
            path = os.path.join(self.directory, name)
            try:
                if now - os.path.getmtime(path) > self.max_age:
                    os.unlink(path)
            except OSError:
                continue

    def count(self):
        try:
            return sum(
                1 for name in os.listdir(self.directory)
                if name.endswith(".json") and not name.startswith(".")
            )
        except OSError:
            return 0
