# modules/bot/motion.py
"""Optional face motion: eye geometry options and wandering.

Two independent ideas live here:

* **Eye geometry** (``eyeSize``, ``eyeGap``, ``eyeOffsetY``) lets the square
  eyes be moved and resized. The same options work for the grid widget, the
  full-screen renderer and the preview endpoint.
* :class:`Wanderer` moves a smaller face around a big panel. It is opt-in and
  pauses while a reaction is held, so an alarm always looks straight at you.
"""
import math
import random

from .schedule import parse_bool

DEFAULT_FACE_SCALE = 0.9
DEFAULT_WANDER_SPEED = 10.0

MIN_FACE_SCALE = 0.2
MAX_FACE_SCALE = 1.0
# A face that fills the panel has nowhere to wander, so keep a little room.
MAX_WANDER_SCALE = 0.85
MAX_WANDER_SPEED = 120.0
MIN_FACE_PX = 12


def _number(value, default, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(low, min(high, number))


def face_scale(settings):
    """Fraction of the short side the full-screen face occupies."""
    return _number(
        (settings or {}).get("botFaceScale"),
        DEFAULT_FACE_SCALE,
        MIN_FACE_SCALE,
        MAX_FACE_SCALE,
    )


def wander_enabled(settings):
    return parse_bool((settings or {}).get("botWanderEnabled"), False)


def wander_speed(settings):
    return _number(
        (settings or {}).get("botWanderSpeed"),
        DEFAULT_WANDER_SPEED,
        0.0,
        MAX_WANDER_SPEED,
    )


def eye_options(settings, config=None, defaults=None):
    """Return the eye geometry options, widget config first, then settings.

    ``defaults`` may supply a third layer (used by the preview endpoint).
    """
    defaults = defaults or {}
    settings = settings or {}
    config = config or {}

    def pick(name, setting_key):
        for source in (config, settings, defaults):
            value = source.get(name, source.get(setting_key))
            if value not in (None, ""):
                return value
        return None

    return {
        "eyeSize": _number(
            pick("eyeSize", "botEyeSize"), 1.0, 0.5, 1.8
        ),
        "eyeGap": _number(
            pick("eyeGap", "botEyeGap"), 0.0, -0.6, 1.0
        ),
        "eyeOffsetY": _number(
            pick("eyeOffsetY", "botEyeOffsetY"), 0.0, -4.0, 4.0
        ),
    }


class Wanderer:
    """Move a square face around a panel, bouncing off the edges.

    The position is kept in pixels for a stable bounce and rescaled when the
    canvas changes size (rotation, a settings reload, a different preview
    size). ``update()`` is deterministic for the timestamps it receives, which
    keeps it testable without real time.
    """

    def __init__(self, speed=DEFAULT_WANDER_SPEED, scale=DEFAULT_FACE_SCALE,
                 seed=7):
        self.speed = _number(speed, DEFAULT_WANDER_SPEED, 0.0, MAX_WANDER_SPEED)
        # Guarantee some travel room even when the panel is small.
        self.scale = min(
            _number(scale, DEFAULT_FACE_SCALE, MIN_FACE_SCALE, MAX_FACE_SCALE),
            MAX_WANDER_SCALE,
        )
        self._rng = random.Random(seed)
        self._x = None
        self._y = None
        self._vx, self._vy = self._random_direction()
        self._free = (0, 0)
        self._canvas = None
        self._now = None
        self._next_turn = self._rng.uniform(2.5, 5.5)

    def _random_direction(self):
        angle = self._rng.uniform(0.0, 2.0 * math.pi)
        return math.cos(angle) * self.speed, math.sin(angle) * self.speed

    def face_size(self, width, height):
        side = min(max(1, int(width)), max(1, int(height)))
        size = int(round(side * self.scale))
        return max(MIN_FACE_PX, min(size, side)), max(MIN_FACE_PX, min(size, side))

    def _place_on_new_canvas(self, width, height, face_w, face_h):
        free_w = max(0, width - face_w)
        free_h = max(0, height - face_h)

        if self._x is None:
            self._x = free_w / 2.0
            self._y = free_h / 2.0
        else:
            old_free_w, old_free_h = self._free
            self._x = (self._x / old_free_w * free_w) if old_free_w else free_w / 2.0
            self._y = (self._y / old_free_h * free_h) if old_free_h else free_h / 2.0

        self._free = (free_w, free_h)

    def _reflect(self, value, speed, limit):
        """Bounce a coordinate inside ``0..limit`` and flip its speed."""
        if limit <= 0:
            return 0.0, 0.0
        if value < 0:
            return -value, abs(speed)
        if value > limit:
            return 2 * limit - value, -abs(speed)
        return value, speed

    def update(self, now, width, height, paused=False):
        """Advance to ``now`` and return ``(x, y, face_w, face_h)``."""
        width = max(1, int(width))
        height = max(1, int(height))
        now = float(now)
        face_w, face_h = self.face_size(width, height)

        if self._canvas != (width, height):
            self._place_on_new_canvas(width, height, face_w, face_h)
            self._canvas = (width, height)

        free_w, free_h = self._free
        dt = 0.0 if self._now is None else max(0.0, min(now - self._now, 0.25))
        self._now = now

        if not paused and dt > 0 and free_w > 0 and free_h > 0:
            self._x += self._vx * dt
            self._y += self._vy * dt
            self._x, self._vx = self._reflect(self._x, self._vx, free_w)
            self._y, self._vy = self._reflect(self._y, self._vy, free_h)

            if now >= self._next_turn:
                self._turn()

        self._x = max(0.0, min(self._x, free_w))
        self._y = max(0.0, min(self._y, free_h))
        return int(round(self._x)), int(round(self._y)), face_w, face_h

    def _turn(self):
        """Nudge the heading, keeping the configured speed."""
        angle = math.atan2(self._vy, self._vx)
        angle += self._rng.uniform(-0.7, 0.7)
        self._vx = math.cos(angle) * self.speed
        self._vy = math.sin(angle) * self.speed
        self._next_turn = self._now + self._rng.uniform(2.5, 6.0)

    def reset(self):
        self._x = None
        self._y = None
        self._canvas = None
        self._now = None
        self._vx, self._vy = self._random_direction()
