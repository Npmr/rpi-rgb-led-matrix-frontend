# modules/bot/face.py
"""Expression model shared by every bot face style.

The model stores continuous expression parameters instead of frames, so the
same mood can be rendered at 32x32 or on a large matrix and can be animated
(blinking, gaze, breathing) without any pre-rendered assets.
"""
import math
import random
from dataclasses import dataclass, replace

# Fields that are interpolated when the mood changes.
_NUMERIC_FIELDS = (
    "eye_left",
    "eye_right",
    "brow_tilt",
    "brow_raise",
    "mouth_curve",
    "mouth_open",
    "mouth_width",
    "gaze_x",
    "gaze_y",
    "blush",
)

# Valid ranges for the params where 0..1 is not enough.
_RANGES = {
    "eye_left": (0.0, 1.0),
    "eye_right": (0.0, 1.0),
    "brow_tilt": (-1.0, 1.0),
    "brow_raise": (-1.0, 1.0),
    "mouth_curve": (-1.0, 1.0),
    "mouth_open": (0.0, 1.0),
    "mouth_width": (0.2, 1.0),
    "gaze_x": (-1.0, 1.0),
    "gaze_y": (-1.0, 1.0),
    "blush": (0.0, 1.0),
}


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Face:
    """A complete facial expression in normalized units.

    ``brow_tilt`` is positive when the inner brow ends are raised (worried,
    sad) and negative when they are lowered (determined, alarmed).
    """

    eye_left: float = 1.0
    eye_right: float = 1.0
    brow_tilt: float = 0.0
    brow_raise: float = 0.0
    mouth_curve: float = 0.15
    mouth_open: float = 0.0
    mouth_width: float = 0.55
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    blush: float = 0.0
    # Filled in by FaceModel.snapshot(); not part of a mood definition.
    bob: float = 0.0


# Mood presets. Keep the names stable: reactions and the web UI use them.
MOODS = {
    "idle": Face(mouth_curve=0.15),
    "happy": Face(
        eye_left=0.9,
        eye_right=0.9,
        brow_raise=0.25,
        mouth_curve=0.85,
        mouth_width=0.72,
        blush=0.35,
    ),
    "excited": Face(
        brow_raise=0.65,
        mouth_curve=0.9,
        mouth_open=0.55,
        mouth_width=0.8,
        blush=0.2,
    ),
    "curious": Face(
        eye_left=0.7,
        eye_right=1.0,
        brow_raise=0.5,
        brow_tilt=0.25,
        mouth_curve=0.3,
        mouth_open=0.18,
        mouth_width=0.42,
        gaze_x=0.45,
    ),
    "thinking": Face(
        eye_left=0.8,
        eye_right=0.8,
        brow_tilt=0.35,
        brow_raise=0.15,
        mouth_curve=-0.15,
        mouth_width=0.38,
        gaze_x=-0.5,
        gaze_y=-0.35,
    ),
    "sad": Face(
        eye_left=0.7,
        eye_right=0.7,
        brow_tilt=0.9,
        brow_raise=-0.1,
        mouth_curve=-0.8,
        mouth_width=0.55,
    ),
    "alarmed": Face(
        brow_raise=0.9,
        mouth_curve=-0.15,
        mouth_open=0.8,
        mouth_width=0.45,
    ),
    "sleepy": Face(
        eye_left=0.12,
        eye_right=0.12,
        brow_raise=-0.2,
        mouth_curve=0.05,
        mouth_open=0.12,
        mouth_width=0.45,
    ),
    "love": Face(
        eye_left=0.85,
        eye_right=0.85,
        brow_raise=0.3,
        mouth_curve=0.9,
        mouth_width=0.65,
        blush=1.0,
    ),
    "wink": Face(
        eye_left=0.95,
        eye_right=0.08,
        mouth_curve=0.75,
        mouth_width=0.65,
        blush=0.4,
    ),
}

MOOD_NAMES = tuple(MOODS)

# How quickly the face eases towards a new mood (seconds).
_EASE_TAU = 0.12
_BLINK_DURATION = 0.16


class FaceModel:
    """Owns the current expression and the small idle animation.

    ``update(now)`` eases the params towards the active mood and schedules
    blinks/saccades. ``snapshot()`` returns a Face with those short-lived
    offsets applied, leaving the stored expression untouched. All animation is
    derived from the timestamps passed in, so a preview or test can render any
    frame deterministically.
    """

    def __init__(self, mood="idle", seed=7, animations=True):
        self.mood = mood if mood in MOODS else "idle"
        self.animations = bool(animations)
        self.face = replace(MOODS[self.mood])
        self._target = replace(MOODS[self.mood])

        self._rng = random.Random(seed)
        self._now = 0.0
        self._last_update = None
        self._sleeping = self.mood == "sleepy"

        self._blink_start = None
        self._next_blink = self._rng.uniform(2.0, 5.0)
        self._saccade = (0.0, 0.0)
        self._saccade_target = (0.0, 0.0)
        self._next_saccade = self._rng.uniform(1.0, 3.0)

    # --- mood control -----------------------------------------------------
    def set_mood(self, mood):
        """Switch to a known mood. Returns False for an unknown name."""
        if mood not in MOODS:
            return False
        self.mood = mood
        self._target = replace(MOODS[mood])
        return True

    def set_sleeping(self, sleeping):
        self._sleeping = bool(sleeping)
        if self._sleeping:
            self.set_mood("sleepy")
        elif self.mood == "sleepy":
            self.set_mood("idle")

    @property
    def sleeping(self):
        return self._sleeping

    def blink(self, now=None):
        """Force a blink (used by tests and the preview tool)."""
        self._blink_start = self._now if now is None else float(now)

    @property
    def is_blinking(self):
        return self._blink_start is not None

    # --- animation --------------------------------------------------------
    def update(self, now):
        now = float(now)
        if self._last_update is None:
            delta = 0.0
        else:
            delta = clamp(now - self._last_update, 0.0, 0.5)
        self._last_update = now
        self._now = now

        # Ease every expression param towards the active mood.
        if delta > 0:
            alpha = 1.0 - math.exp(-delta / _EASE_TAU)
            for field in _NUMERIC_FIELDS:
                current = getattr(self.face, field)
                target = getattr(self._target, field)
                low, high = _RANGES[field]
                setattr(
                    self.face,
                    field,
                    clamp(current + (target - current) * alpha, low, high),
                )

        self._update_blink(now)
        self._update_saccade(now, delta)

    def _update_blink(self, now):
        # An explicit blink() still works when idle animations are disabled.
        if self._sleeping:
            self._blink_start = None
            return

        if self._blink_start is None and self.animations and now >= self._next_blink:
            self._blink_start = now

        if self._blink_start is not None and now - self._blink_start >= _BLINK_DURATION:
            self._blink_start = None
            self._next_blink = now + self._rng.uniform(2.5, 6.5)

    def _update_saccade(self, now, delta):
        if not self.animations:
            self._saccade = (0.0, 0.0)
            return

        if self._sleeping:
            self._saccade_target = (0.0, 0.0)
        elif now >= self._next_saccade:
            self._saccade_target = (
                self._rng.uniform(-0.45, 0.45),
                self._rng.uniform(-0.25, 0.25),
            )
            self._next_saccade = now + self._rng.uniform(1.5, 4.5)

        if delta > 0:
            alpha = 1.0 - math.exp(-delta / 0.06)
            self._saccade = (
                self._saccade[0] + (self._saccade_target[0] - self._saccade[0]) * alpha,
                self._saccade[1] + (self._saccade_target[1] - self._saccade[1]) * alpha,
            )

    def snapshot(self):
        """Return the expression with blink/gaze/bob applied."""
        face = replace(self.face)

        if self._blink_start is not None:
            progress = clamp(
                (self._now - self._blink_start) / _BLINK_DURATION, 0.0, 1.0
            )
            factor = 1.0 - math.sin(math.pi * progress)
            face.eye_left = clamp(face.eye_left * factor, 0.0, 1.0)
            face.eye_right = clamp(face.eye_right * factor, 0.0, 1.0)

        if not self.animations:
            face.bob = 0.0
            return face

        if self._sleeping:
            face.gaze_x = clamp(face.gaze_x, -1.0, 1.0)
            face.gaze_y = clamp(face.gaze_y, -1.0, 1.0)
            face.bob = math.sin(self._now * 0.7) * 0.4
        else:
            face.gaze_x = clamp(face.gaze_x + self._saccade[0], -1.0, 1.0)
            face.gaze_y = clamp(face.gaze_y + self._saccade[1], -1.0, 1.0)
            face.bob = math.sin(self._now * 1.6) * 0.55
        return face
