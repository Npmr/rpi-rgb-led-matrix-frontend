# modules/widgets/image.py
"""Picture widget: still images and animated GIF/WebP files.

Frames are decoded once and pre-scaled to the widget rectangle, so the render
loop only pastes a ready-made image. That keeps animated GIFs cheap on a
Raspberry Pi, where resizing every frame at 30 fps would be far too slow.
"""
import math
import os

from PIL import Image

from .base import Widget
from ..surface import Surface

# Cap the decoded frames so a huge GIF cannot exhaust the memory of a Pi.
MAX_FRAMES = 150
MIN_FRAME_MS = 20
DEFAULT_FRAME_MS = 100


def _is_safe_filename(filename):
    if not filename:
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return os.path.basename(filename) == filename


class ImageWidget(Widget):
    type_id = "image"

    def __init__(self, spec, context):
        super().__init__(spec, context)
        self.filename = self.config.get("filename", "")
        self.fit = self.style.get("fit", "cover")
        self._frames = None
        self._durations = None
        self._total_ms = 0
        self._mtime = None
        self._size = None
        self._started = None
        self._now = None

    def _path(self):
        if not _is_safe_filename(self.filename):
            return None
        return os.path.join(self.context.static_pictures_dir, self.filename)

    # --- loading ----------------------------------------------------------
    def _load(self, size):
        """Decode and pre-scale every frame. Returns True when frames exist."""
        path = self._path()
        if not path:
            return False

        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return False

        if (self._frames and self._mtime == mtime and self._size == size):
            return True

        frame_count = 1
        try:
            with Image.open(path) as opened:
                frame_count = getattr(opened, "n_frames", 1) or 1
                # Keep every n-th frame when a GIF has more frames than the cap,
                # stretching the delays so the animation keeps its speed.
                step = max(1, int(math.ceil(frame_count / MAX_FRAMES)))
                frames = []
                durations = []
                for index in range(0, frame_count, step):
                    opened.seek(index)
                    frame = opened.convert("RGB")
                    surface = Surface(size[0], size[1])
                    surface.draw_image(frame, 0, 0, size[0], size[1],
                                       fit=self.fit)
                    frames.append(surface.image)
                    durations.append(self._frame_delay(opened) * step)
        except (OSError, ValueError) as error:
            print(f"Image widget: could not load {path}: {error}")
            self._frames = None
            self._mtime = None
            return False

        self._frames = frames
        self._durations = durations
        self._total_ms = sum(durations)
        self._mtime = mtime
        self._size = size
        return bool(frames)

    @staticmethod
    def _frame_delay(opened):
        try:
            delay = int(opened.info.get("duration", DEFAULT_FRAME_MS))
        except (TypeError, ValueError):
            delay = DEFAULT_FRAME_MS
        return max(MIN_FRAME_MS, delay)

    # --- widget hooks -----------------------------------------------------
    def update(self, now):
        self._now = now
        if self._started is None:
            self._started = now

    def render(self, surface, rect):
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return
        if not self._load((int(w), int(h))):
            return
        surface.image.paste(self._frames[self._current_index()], (int(x), int(y)))

    def _current_index(self):
        if not self._frames:
            return 0
        if len(self._frames) == 1 or self._total_ms <= 0:
            return 0
        now = self._now if self._now is not None else 0.0
        if self._started is None:
            self._started = now
        elapsed = (now - self._started) * 1000.0
        position = elapsed % self._total_ms
        for index, duration in enumerate(self._durations):
            if position < duration:
                return index
            position -= duration
        return len(self._frames) - 1

    def stop(self):
        self._frames = None
        self._durations = None
        self._mtime = None
