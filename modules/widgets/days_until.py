# modules/widgets/days_until.py
"""Countdown widget: days until a fixed or recurring date (e.g. Christmas)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .base import Widget
from ..surface import load_font


def resolve_target(today, month, day, year=None, recurring=True):
    """Return (days_remaining, target_date) or (None, None) for invalid dates.

    ``days_remaining`` is 0 on the event day. When ``recurring`` is true the
    target rolls forward to the next occurrence; when an explicit ``year`` is
    given and already passed, the remaining days are negative.
    """
    year = int(year) if year else None
    month = int(month)
    day = int(day)

    if year is not None:
        try:
            target = date(year, month, day)
        except ValueError:
            return None, None
        return (target - today).days, target

    try:
        target = date(today.year, month, day)
    except ValueError:
        return None, None

    if recurring:
        # Roll forward until the target is today or later.
        for _ in range(2):
            if target >= today:
                break
            try:
                target = target.replace(year=target.year + 1)
            except ValueError:
                # Feb 29 in a non-leap year -> fall back to Feb 28.
                target = date(target.year + 1, month, 28)
    elif target < today:
        return (target - today).days, target

    return (target - today).days, target


class DaysUntilWidget(Widget):
    type_id = "days_until"

    def __init__(self, spec, context):
        super().__init__(spec, context)
        self.month = self.config.get("month", 12)
        self.day = self.config.get("day", 25)
        self.year = self.config.get("year")
        self.recurring = bool(self.config.get("recurring", True))
        self.label = self.config.get("label", "")
        self.template = self.config.get("template") or "{days}d {label}"
        self.finished_text = self.config.get("finishedText", "")
        self._text = ""

    def _zone(self):
        try:
            return ZoneInfo(self.context.timezone)
        except Exception:
            return ZoneInfo("UTC")

    def build_text(self, today):
        days, _target = resolve_target(
            today, self.month, self.day, self.year, self.recurring
        )
        if days is None:
            return "--"

        if days == 0 and self.finished_text:
            return self.finished_text

        if self.year is not None and days < 0:
            return self.finished_text or f"{-days}d ago"

        try:
            text = self.template.format(days=days, label=self.label)
        except (KeyError, IndexError, ValueError):
            text = f"{days}d {self.label}"
        return text.strip()

    def update(self, now):
        today = datetime.fromtimestamp(now, self._zone()).date()
        self._text = self.build_text(today)

    def render(self, surface, rect):
        x, y, w, h = rect
        if not self._text:
            return
        surface.draw_text(x, y, w, h, self._text, self.color, load_font(h), self.align)
