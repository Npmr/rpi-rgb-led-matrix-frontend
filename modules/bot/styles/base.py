# modules/bot/styles/base.py
"""Shared drawing helpers for bot face styles.

Styles draw on a virtual 32x32 grid which is scaled to the real widget size.
That keeps the 32x32 layout crisp and lets the same coordinates grow to a large
matrix without any bitmap assets.
"""
from PIL import Image, ImageDraw

DESIGN_SIZE = 32


def parse_color(value, default):
    """Parse ``#rrggbb``, ``rgb(...)``-less ``r,g,b`` or a sequence."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return tuple(max(0, min(255, int(component))) for component in value[:3])
        except (TypeError, ValueError):
            return tuple(default)

    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            text = text[1:]
            try:
                if len(text) == 3:
                    return tuple(int(part * 2, 16) for part in text)
                if len(text) >= 6:
                    return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))
            except ValueError:
                return tuple(default)
        elif "," in text:
            parts = [part.strip() for part in text.split(",")]
            if len(parts) >= 3:
                try:
                    return tuple(
                        max(0, min(255, int(part))) for part in parts[:3]
                    )
                except ValueError:
                    return tuple(default)
    return tuple(default)


def blend(first, second, amount):
    """Mix ``first`` towards ``second`` by ``amount`` (0..1)."""
    amount = max(0.0, min(1.0, float(amount)))
    return tuple(
        int(round(a + (b - a) * amount)) for a, b in zip(first[:3], second[:3])
    )


def rgba(color):
    if len(color) >= 4:
        return tuple(int(component) for component in color[:4])
    return (int(color[0]), int(color[1]), int(color[2]), 255)


def _float_option(value, default, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(low, min(high, number))


def eye_options(options):
    """Return ``(scale, gap, offset_y)`` for the eyes.

    ``eyeSize`` scales both eye axes (1.0 = the style's normal eye), ``eyeGap``
    moves the eyes apart (negative moves them together) and ``eyeOffsetY``
    shifts them up or down. Values are clamped so a hand-edited layout.json can
    never push the eyes outside the design canvas.
    """
    options = options or {}
    scale = _float_option(options.get("eyeSize"), 1.0, 0.5, 1.8)
    gap = _float_option(options.get("eyeGap"), 0.0, -0.6, 1.0) * 2.5
    offset_y = _float_option(options.get("eyeOffsetY"), 0.0, -4.0, 4.0)
    return scale, gap, offset_y


class StyleCanvas:
    """An RGBA tile with a virtual 32x32 coordinate system."""

    def __init__(self, width, height, background=None):
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.image = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

        self.unit = min(self.width, self.height)
        self.scale = self.unit / float(DESIGN_SIZE)
        self.offset_x = (self.width - self.unit) / 2.0
        self.offset_y = (self.height - self.unit) / 2.0

        if background is not None:
            self.draw.rectangle(
                [0, 0, self.width - 1, self.height - 1],
                fill=rgba(background),
            )

    # --- coordinate helpers ----------------------------------------------
    def _x(self, value):
        return int(round(self.offset_x + value * self.scale))

    def _y(self, value):
        return int(round(self.offset_y + value * self.scale))

    def _width(self, value):
        return max(1, int(round(value * self.scale)))

    def rectangle(self, x0, y0, x1, y1, fill):
        if x1 <= x0 or y1 <= y0:
            return
        self.draw.rectangle(
            [self._x(x0), self._y(y0), self._x(x1) - 1, self._y(y1) - 1],
            fill=rgba(fill),
        )

    def rounded_rectangle(self, x0, y0, x1, y1, radius, fill=None, outline=None,
                          width=1):
        if x1 <= x0 or y1 <= y0:
            return
        self.draw.rounded_rectangle(
            [self._x(x0), self._y(y0), self._x(x1) - 1, self._y(y1) - 1],
            radius=max(0, int(round(radius * self.scale))),
            fill=rgba(fill) if fill is not None else None,
            outline=rgba(outline) if outline is not None else None,
            width=self._width(width),
        )

    def ellipse(self, cx, cy, rx, ry, fill):
        if rx <= 0 or ry <= 0:
            return
        self.draw.ellipse(
            [
                self._x(cx - rx),
                self._y(cy - ry),
                self._x(cx + rx) - 1,
                self._y(cy + ry) - 1,
            ],
            fill=rgba(fill),
        )

    def circle(self, cx, cy, radius, fill):
        self.ellipse(cx, cy, radius, radius, fill)

    def line(self, x0, y0, x1, y1, fill, width=1):
        self.draw.line(
            [self._x(x0), self._y(y0), self._x(x1), self._y(y1)],
            fill=rgba(fill),
            width=self._width(width),
        )

    def polyline(self, points, fill, width=1):
        if len(points) < 2:
            return
        self.draw.line(
            [(self._x(x), self._y(y)) for x, y in points],
            fill=rgba(fill),
            width=self._width(width),
        )

    def arc(self, x0, y0, x1, y1, start, end, fill, width=1):
        self.draw.arc(
            [self._x(x0), self._y(y0), self._x(x1) - 1, self._y(y1) - 1],
            start,
            end,
            fill=rgba(fill),
            width=self._width(width),
        )

    def pieslice(self, x0, y0, x1, y1, start, end, fill):
        self.draw.pieslice(
            [self._x(x0), self._y(y0), self._x(x1) - 1, self._y(y1) - 1],
            start,
            end,
            fill=rgba(fill),
        )

    def polygon(self, points, fill):
        if len(points) < 3:
            return
        self.draw.polygon(
            [(self._x(x), self._y(y)) for x, y in points],
            fill=rgba(fill),
        )
