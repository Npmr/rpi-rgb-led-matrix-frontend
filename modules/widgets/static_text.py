# modules/widgets/static_text.py
"""Static (optionally scrolling) text widget."""
from .base import Widget
from ..surface import load_font


class StaticTextWidget(Widget):
    type_id = "static_text"

    def __init__(self, spec, context):
        super().__init__(spec, context)
        self.text = self.config.get("text", "")
        self.scroll = bool(self.config.get("scroll", False))
        try:
            self.speed = max(1.0, float(self.config.get("speed", 20)))
        except (TypeError, ValueError):
            self.speed = 20.0
        self._now = 0.0

    def update(self, now):
        self._now = now

    def render(self, surface, rect):
        x, y, w, h = rect
        if not self.text or w <= 0 or h <= 0:
            return

        font = load_font(h)
        if not self.scroll:
            surface.draw_text(x, y, w, h, self.text, self.color, font, self.align)
            return

        text_width = surface.measure_text(self.text, font)
        span = text_width + w
        if span <= 0:
            return
        offset = -int((self._now * self.speed) % span)
        surface.draw_text(
            x, y, w, h, self.text, self.color, font, align="left", offset_x=offset
        )
