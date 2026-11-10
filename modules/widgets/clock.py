# modules/widgets/clock.py
"""Time and date widget."""
from datetime import datetime
from zoneinfo import ZoneInfo

from .base import Widget
from ..surface import load_font


class ClockWidget(Widget):
    type_id = "clock"

    def __init__(self, spec, context):
        super().__init__(spec, context)
        settings = context.settings
        self.time_format = (
            self.config.get("timeFormat")
            or settings.get("clockFormatTime", "%H:%M:%S")
        )
        self.date_format = (
            self.config.get("dateFormat")
            or settings.get("clockFormatDate", "%A")
        )
        self._time = ""
        self._date = ""

    def _zone(self):
        try:
            return ZoneInfo(self.context.timezone)
        except Exception:
            return ZoneInfo("UTC")

    def update(self, now):
        moment = datetime.fromtimestamp(now, self._zone())
        self._time = moment.strftime(self.time_format) if self.time_format else ""
        self._date = moment.strftime(self.date_format) if self.date_format else ""

    def render(self, surface, rect):
        x, y, w, h = rect
        if not self._time and not self._date:
            return
        if not self._date or h < 16:
            text = self._time or self._date
            surface.draw_text(x, y, w, h, text, self.color, load_font(h), self.align)
            return

        time_height = max(1, int(h * 0.62))
        date_height = max(1, h - time_height)
        surface.draw_text(
            x, y, w, time_height, self._time, self.color,
            load_font(time_height), self.align,
        )
        surface.draw_text(
            x, y + time_height, w, date_height, self._date, self.color,
            load_font(date_height), self.align,
        )
