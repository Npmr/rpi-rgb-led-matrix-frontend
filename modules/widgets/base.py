# modules/widgets/base.py
"""Base class and shared context for grid widgets."""
import os

from ..geometry import get_display_geometry


class WidgetContext:
    """Per-render shared state handed to every widget.

    The grid (columns, rows, cell size) is derived from the hardware settings
    via :func:`get_display_geometry`; it is never stored in ``layout.json``.
    """

    def __init__(self, settings, layout, geometry=None, width=None, height=None):
        self.settings = settings or {}
        self.layout = layout or {}
        self.geometry = geometry or get_display_geometry(self.settings)
        self.width = int(
            width if width is not None else self.geometry["width"]
        )
        self.height = int(
            height if height is not None else self.geometry["height"]
        )
        self.cell_w = int(self.geometry["cellW"])
        self.cell_h = int(self.geometry["cellH"])
        self.cols = int(self.geometry["cols"])
        self.rows = int(self.geometry["rows"])

        # One bot engine is shared by every bot widget in this frame context.
        # Events are drained once per frame instead of once per widget.
        self._bot_engine = None
        self._bot_updated_at = None

    @property
    def bot_engine(self):
        """Lazily create the bot engine used by all bot widgets."""
        if self._bot_engine is None:
            from ..bot.engine import BotEngine

            self._bot_engine = BotEngine(self.settings)
        return self._bot_engine

    def update_bot(self, now):
        """Advance the shared bot engine at most once per frame timestamp."""
        if self._bot_updated_at != now:
            self.bot_engine.update(now)
            self._bot_updated_at = now

    def bot_status(self):
        """Return the engine state, or ``{}`` when no bot widget exists."""
        if self._bot_engine is None:
            return {}
        return self._bot_engine.state()

    @property
    def timezone(self):
        return self.settings.get("timezone", "UTC") or "UTC"

    @property
    def static_pictures_dir(self):
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "static", "pictures")
        )

    def widget_pixel_rect(self, spec):
        """Return the pixel rectangle (x, y, w, h) for a widget spec."""
        col = int(spec.get("col", 0))
        row = int(spec.get("row", 0))
        width = int(spec.get("w", 1))
        height = int(spec.get("h", 1))
        return (
            col * self.cell_w,
            row * self.cell_h,
            width * self.cell_w,
            height * self.cell_h,
        )


class Widget:
    """Base widget. Subclasses implement update() and render()."""

    type_id = "base"

    def __init__(self, spec, context):
        self.spec = spec
        self.context = context
        self.id = spec.get("id")
        self.config = spec.get("config") or {}
        self.style = spec.get("style") or {}
        self.color = tuple(int(c) for c in self.style.get("color", (255, 255, 255))[:3])
        self.align = self.style.get("align", "center")

    # Lifecycle hooks ------------------------------------------------------
    def start(self):
        """Called once after creation (before the first frame)."""

    def update(self, now):
        """Called every frame; ``now`` is a ``time.time()`` timestamp."""

    def render(self, surface, rect):
        """Draw the widget into ``rect`` = (x, y, w, h)."""

    def stop(self):
        """Called when the widget is removed or the renderer shuts down."""

    # Helpers --------------------------------------------------------------
    def pixel_rect(self):
        return self.context.widget_pixel_rect(self.spec)
