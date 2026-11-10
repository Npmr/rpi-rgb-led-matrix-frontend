# modules/widgets/registry.py
"""Widget type registry."""
from .base import Widget
from .api_text import ApiTextWidget
from .clock import ClockWidget
from .days_until import DaysUntilWidget
from .image import ImageWidget
from .static_text import StaticTextWidget

_REGISTRY = {}


def register(widget_class):
    if not issubclass(widget_class, Widget):
        raise TypeError("Only Widget subclasses can be registered")
    _REGISTRY[widget_class.type_id] = widget_class
    return widget_class


for _widget in (
    ClockWidget,
    DaysUntilWidget,
    ApiTextWidget,
    StaticTextWidget,
    ImageWidget,
):
    register(_widget)


def available_types():
    return sorted(_REGISTRY.keys())


def create_widget(spec, context):
    """Instantiate the widget described by ``spec`` or return None."""
    widget_class = _REGISTRY.get(spec.get("type"))
    if widget_class is None:
        return None
    return widget_class(spec, context)


def build_widgets(layout, context):
    """Create and start every widget in a layout. Errors are skipped."""
    widgets = []
    for spec in layout.get("widgets", []):
        widget = create_widget(spec, context)
        if widget is None:
            print(f"Grid: skipping unknown widget type {spec.get('type')!r}")
            continue
        try:
            widget.start()
        except Exception as error:
            print(f"Grid: failed to start widget {spec.get('id')!r}: {error}")
        widgets.append(widget)
    return widgets


def stop_widgets(widgets):
    for widget in widgets:
        try:
            widget.stop()
        except Exception as error:
            print(f"Grid: failed to stop widget {widget.id!r}: {error}")
