# modules/layout_handler.py
"""Read, validate and persist the grid layout configuration (layout.json).

The grid layout is kept separate from settings.json so that the grid renderer
can hot-reload it independently of the main application settings.
"""
import copy
import json
import os
import uuid

LAYOUT_FILENAME = "layout.json"

# Widget types that the renderer/registry knows about.
WIDGET_TYPES = ("clock", "days_until", "api_text", "static_text", "image")

DEFAULT_LAYOUT = {
    "enabled": False,
    "grid": {
        "showBorders": False,
        "borderColor": [40, 40, 40],
        "backgroundColor": [0, 0, 0],
    },
    "widgets": [],
}


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_layout():
    """Return a fresh copy of the default layout."""
    return copy.deepcopy(DEFAULT_LAYOUT)


def _normalize_color(value, fallback):
    """Coerce a value into an [r, g, b] list clamped to 0-255."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return list(fallback)
    result = []
    for component in value:
        try:
            result.append(max(0, min(255, int(component))))
        except (TypeError, ValueError):
            return list(fallback)
    return result


def _coerce_int(value, default, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def read_layout(filename=LAYOUT_FILENAME):
    """Read layout.json, falling back to defaults on any error."""
    filepath = filename
    if not os.path.isabs(filepath):
        filepath = os.path.join(_project_root(), filename)
    try:
        with open(filepath, "r") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return default_layout()
    except (json.JSONDecodeError, OSError) as error:
        print(f"Error: could not read layout file {filepath}: {error}")
        return default_layout()

    if not isinstance(data, dict):
        return default_layout()

    layout = default_layout()
    layout["enabled"] = bool(data.get("enabled", False))

    grid = data.get("grid")
    if isinstance(grid, dict):
        layout["grid"]["showBorders"] = bool(grid.get("showBorders", False))
        layout["grid"]["borderColor"] = _normalize_color(
            grid.get("borderColor"), (40, 40, 40)
        )
        layout["grid"]["backgroundColor"] = _normalize_color(
            grid.get("backgroundColor"), (0, 0, 0)
        )

    widgets = data.get("widgets")
    if isinstance(widgets, list):
        layout["widgets"] = [w for w in widgets if isinstance(w, dict)]

    return layout


def save_layout(layout, filename=LAYOUT_FILENAME):
    """Persist a layout dictionary as JSON. Returns True on success."""
    filepath = filename
    if not os.path.isabs(filepath):
        filepath = os.path.join(_project_root(), filename)
    try:
        with open(filepath, "w") as handle:
            json.dump(layout, handle, indent=4)
        return True
    except OSError as error:
        print(f"Error: could not write layout file {filepath}: {error}")
        return False


def grid_dimensions(geometry):
    """Return (cols, rows, cell_w, cell_h) from a display geometry dict."""
    return (
        geometry["cols"],
        geometry["rows"],
        geometry["cellW"],
        geometry["cellH"],
    )


def _rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def validate_layout(layout, geometry):
    """Validate and normalize a layout against the display geometry.

    Returns ``(normalized_layout, errors)``. When ``errors`` is non-empty the
    caller should not persist the layout.
    """
    errors = []
    if not isinstance(layout, dict):
        return default_layout(), ["Layout must be a JSON object"]

    normalized = default_layout()
    normalized["enabled"] = bool(layout.get("enabled", False))

    grid = layout.get("grid", {})
    if not isinstance(grid, dict):
        grid = {}

    normalized["grid"] = {
        "showBorders": bool(grid.get("showBorders", False)),
        "borderColor": _normalize_color(grid.get("borderColor"), (40, 40, 40)),
        "backgroundColor": _normalize_color(
            grid.get("backgroundColor"), (0, 0, 0)
        ),
    }

    cols, rows, _cell_w, _cell_h = grid_dimensions(geometry)

    widgets = layout.get("widgets", [])
    if not isinstance(widgets, list):
        errors.append("Widgets must be a list")
        widgets = []

    occupied = []
    normalized_widgets = []
    for index, raw in enumerate(widgets):
        if not isinstance(raw, dict):
            errors.append(f"Widget #{index} is not an object")
            continue

        widget_type = raw.get("type")
        if widget_type not in WIDGET_TYPES:
            errors.append(f"Widget #{index} has unknown type {widget_type!r}")
            continue

        width = _coerce_int(raw.get("w"), 1, minimum=1, maximum=cols)
        height = _coerce_int(raw.get("h"), 1, minimum=1, maximum=rows)
        col = _coerce_int(raw.get("col"), 0)
        row = _coerce_int(raw.get("row"), 0)
        col = max(0, min(col, cols - width))
        row = max(0, min(row, rows - height))

        rect = (col, row, width, height)
        for other_id, other_rect in occupied:
            if _rects_overlap(rect, other_rect):
                errors.append(
                    f"Widget {raw.get('id', index)!r} overlaps widget {other_id!r}"
                )
                break

        widget_id = raw.get("id")
        if not isinstance(widget_id, str) or not widget_id:
            widget_id = f"w{uuid.uuid4().hex[:8]}"

        style = raw.get("style", {})
        if not isinstance(style, dict):
            style = {}
        config = raw.get("config", {})
        if not isinstance(config, dict):
            config = {}

        normalized_widgets.append(
            {
                "id": widget_id,
                "type": widget_type,
                "col": col,
                "row": row,
                "w": width,
                "h": height,
                "style": {
                    "color": _normalize_color(style.get("color"), (255, 255, 255)),
                    "align": style.get("align", "center"),
                    "fit": style.get("fit", "cover"),
                },
                "config": config,
            }
        )
        occupied.append((widget_id, rect))

    normalized["widgets"] = normalized_widgets
    return normalized, errors


def new_widget(widget_type, col=0, row=0, width=1, height=1):
    """Create a widget skeleton with sensible defaults for the given type."""
    defaults = {
        "clock": {
            "style": {"color": [255, 255, 255], "align": "center"},
            "config": {"timeFormat": "", "dateFormat": ""},
        },
        "days_until": {
            "style": {"color": [255, 60, 60], "align": "center"},
            "config": {
                "month": 12,
                "day": 25,
                "year": None,
                "recurring": True,
                "label": "XMAS",
                "template": "{days}d {label}",
                "finishedText": "MERRY XMAS",
            },
        },
        "api_text": {
            "style": {"color": [255, 255, 0], "align": "center"},
            "config": {
                "url": "",
                "method": "GET",
                "jsonPath": "",
                "regex": "",
                "interval": 300,
                "timeout": 10,
                "decimals": 0,
                "prefix": "",
                "suffix": "",
                "errorText": "N/A",
            },
        },
        "static_text": {
            "style": {"color": [0, 255, 120], "align": "left"},
            "config": {"text": "Hello", "scroll": False, "speed": 20},
        },
        "image": {
            "style": {"fit": "cover"},
            "config": {"filename": ""},
        },
    }
    template = copy.deepcopy(defaults.get(widget_type, {"style": {}, "config": {}}))
    widget = {
        "id": f"w{uuid.uuid4().hex[:8]}",
        "type": widget_type,
        "col": col,
        "row": row,
        "w": width,
        "h": height,
    }
    widget.update(template)
    return widget
