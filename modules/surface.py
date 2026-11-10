# modules/surface.py
"""A tiny drawing surface used by grid widgets.

The whole frame is composed with Pillow and then blitted to the LED matrix with
``FrameCanvas.SetImage``. Composing with Pillow gives us exact clipping, easy
image drawing and a render path that can be unit-tested without any hardware.
"""
import os

from PIL import Image, ImageDraw, ImageFont

# Largest first; the first font whose height fits the requested height wins.
_FONT_CANDIDATES = [
    ("10x20.bdf", 20),
    ("9x18B.bdf", 18),
    ("7x13.bdf", 13),
    ("6x10.bdf", 10),
    ("5x8.bdf", 8),
    ("4x6.bdf", 6),
]

_FONT_CACHE = {}


def _font_dir():
    base_matrix_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "rpi-rgb-led-matrix")
    )
    return os.path.join(base_matrix_dir, "fonts")


def font_path_for_height(height):
    """Return (path, pixel_height) of the best fitting bitmap font."""
    fonts_dir = _font_dir()
    for filename, pixel_height in _FONT_CANDIDATES:
        if pixel_height <= height:
            return os.path.join(fonts_dir, filename), pixel_height
    filename, pixel_height = _FONT_CANDIDATES[-1]
    return os.path.join(fonts_dir, filename), pixel_height


def load_font(height):
    """Load (and cache) a PIL font sized for the given pixel height."""
    path, pixel_height = font_path_for_height(height)
    key = (path, pixel_height)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, pixel_height)
    return _FONT_CACHE[key]


def _rgba(color):
    """Convert an (r, g, b) or (r, g, b, a) sequence to a 4-tuple."""
    if len(color) == 4:
        return tuple(int(c) for c in color)
    return (int(color[0]), int(color[1]), int(color[2]), 255)


class Surface:
    """RGB drawing surface with text, rectangle and image helpers."""

    def __init__(self, width, height):
        self.width = int(width)
        self.height = int(height)
        self.image = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        self._draw = ImageDraw.Draw(self.image)

    # --- basic operations -------------------------------------------------
    def clear(self, color=(0, 0, 0)):
        self._draw.rectangle(
            [0, 0, self.width - 1, self.height - 1], fill=tuple(color)
        )

    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        self._draw.rectangle(
            [x, y, x + w - 1, y + h - 1], fill=tuple(color)
        )

    def set_pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self._draw.point((x, y), fill=tuple(color))

    def line(self, x1, y1, x2, y2, color):
        self._draw.line([x1, y1, x2, y2], fill=tuple(color))

    # --- text -------------------------------------------------------------
    def measure_text(self, text, font):
        if not text:
            return 0
        left, top, right, bottom = self._draw.textbbox((0, 0), text, font=font)
        return right - left

    def draw_text(self, x, y, w, h, text, color, font, align="center", offset_x=0):
        """Draw text clipped to the rectangle (x, y, w, h).

        ``offset_x`` shifts the text inside the rectangle and is used for
        scrolling. Alignment is applied within the rectangle.
        """
        if not text or w <= 0 or h <= 0:
            return 0

        # Draw onto a transparent tile so anything outside the rect is clipped.
        tile = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
        tile_draw = ImageDraw.Draw(tile)

        left, top, right, bottom = tile_draw.textbbox((0, 0), text, font=font)
        text_width = right - left
        text_height = bottom - top

        if align == "left":
            tx = offset_x - left
        elif align == "right":
            tx = offset_x + (w - text_width) - left
        else:
            tx = offset_x + (w - text_width) // 2 - left

        ty = (h - text_height) // 2 - top
        tile_draw.text((tx, ty), text, font=font, fill=_rgba(color))

        self.image.paste(tile, (int(x), int(y)), tile)
        return text_width

    def draw_text_lines(self, x, y, w, h, lines, color):
        """Draw multiple lines, each auto-sized to a share of the height."""
        if not lines:
            return
        line_height = max(1, h // len(lines))
        for index, text in enumerate(lines):
            font = load_font(line_height)
            self.draw_text(
                x, y + index * line_height, w, line_height, text, color, font
            )

    # --- images -----------------------------------------------------------
    def draw_image(self, image, x, y, w, h, fit="cover", background=(0, 0, 0)):
        if w <= 0 or h <= 0:
            return
        if image.mode != "RGB":
            image = image.convert("RGB")

        if fit == "contain":
            ratio = min(w / image.width, h / image.height)
        else:
            ratio = max(w / image.width, h / image.height)

        new_size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
        resized = image.resize(new_size, Image.Resampling.LANCZOS)

        # Center-crop (or letterbox) into the target rectangle.
        left = max(0, (resized.width - w) // 2)
        top = max(0, (resized.height - h) // 2)
        crop = resized.crop((left, top, left + w, top + h))

        tile = Image.new("RGB", (int(w), int(h)), tuple(background))
        tile.paste(crop, ((int(w) - crop.width) // 2, (int(h) - crop.height) // 2))
        self.image.paste(tile, (int(x), int(y)))

    def draw_grid_border(self, x, y, w, h, color):
        if w <= 1 or h <= 1:
            return
        self.line(x, y, x + w - 1, y, color)
        self.line(x, y + h - 1, x + w - 1, y + h - 1, color)
        self.line(x, y, x, y + h - 1, color)
        self.line(x + w - 1, y, x + w - 1, y + h - 1, color)

    def to_rgb(self):
        return self.image
