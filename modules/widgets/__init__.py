# modules/widgets/__init__.py
"""Grid display widgets."""
from .base import Widget, WidgetContext
from .registry import (
    available_types,
    build_widgets,
    create_widget,
    register,
    stop_widgets,
)

__all__ = [
    "Widget",
    "WidgetContext",
    "available_types",
    "build_widgets",
    "create_widget",
    "register",
    "stop_widgets",
]
