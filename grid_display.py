#!/usr/bin/env python3
"""Grid display renderer.

Runs as a standalone process (the RGB matrix can only be owned by one process
at a time). It reads the layout from ``layout.json``, hot-reloads it when the
file changes and composes each frame with Pillow before blitting it to the
panel.

Usage:
    sudo python3 grid_display.py
"""
import os
import signal
import sys
import time

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:  # pragma: no cover - hardware dependency
    RGBMatrix = None
    RGBMatrixOptions = None

from modules.display_control import (
    get_base_rotation,
    get_pixel_mapper_config,
)
from modules.geometry import get_display_geometry
from modules.layout_handler import read_layout
from modules.settings_handler import read_settings
from modules.surface import Surface
from modules.widgets.base import WidgetContext
from modules.widgets.registry import build_widgets, stop_widgets

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LAYOUT_PATH = os.path.join(PROJECT_ROOT, "layout.json")

# Cap the compose rate; the panel refresh via SwapOnVSync may be faster.
FRAME_INTERVAL = 1.0 / 30.0


def _int_setting(settings, key, default):
    try:
        return int(settings.get(key, default))
    except (TypeError, ValueError):
        return default


def build_matrix(settings):
    """Create the RGBMatrix using the same options as the CLI viewers."""
    if RGBMatrix is None:
        raise RuntimeError(
            "The rgbmatrix Python bindings are not installed. "
            "Install them with: pip install ./bindings/python"
        )

    rows = _int_setting(settings, "heightInPixel", 32)
    cols = _int_setting(settings, "widthInPixel", 32)
    chain = _int_setting(settings, "chainLength", 1)
    parallel = _int_setting(settings, "parallelChains", 1)
    brightness = _int_setting(settings, "displayBrightness", 100)
    slowdown = _int_setting(settings, "ledSlowdown", 2)

    rotation = get_base_rotation(settings) % 360
    pixel_mapper = get_pixel_mapper_config(settings, rotation)

    options = RGBMatrixOptions()
    options.rows = rows
    options.cols = cols
    options.chain_length = chain
    options.parallel = parallel
    options.brightness = brightness
    options.gpio_slowdown = slowdown
    options.pixel_mapper_config = pixel_mapper
    return RGBMatrix(options=options)


def _layout_mtime():
    try:
        return os.path.getmtime(LAYOUT_PATH)
    except OSError:
        return None


def _draw_grid_borders(surface, layout, context):
    color = tuple(layout["grid"].get("borderColor", (40, 40, 40)))
    for row in range(context.rows):
        for col in range(context.cols):
            surface.draw_grid_border(
                col * context.cell_w,
                row * context.cell_h,
                context.cell_w,
                context.cell_h,
                color,
            )


def run():
    settings = read_settings()
    geometry = get_display_geometry(settings)
    matrix = build_matrix(settings)

    matrix_width, matrix_height = matrix.width, matrix.height
    if (matrix_width, matrix_height) != (geometry["width"], geometry["height"]):
        # The driver is the ground truth; keep it but make mapper drift visible.
        print(
            f"Grid: driver reports {matrix_width}x{matrix_height}, "
            f"settings-derived geometry is {geometry['width']}x{geometry['height']} "
            f"({geometry['pixelMapper']})"
        )

    layout = read_layout()
    layout_mtime = _layout_mtime()
    # The grid always follows the settings-derived geometry so the editor and
    # the renderer agree; width/height only size the drawing surface.
    context = WidgetContext(
        settings, layout, geometry=geometry,
        width=matrix_width, height=matrix_height,
    )
    widgets = build_widgets(layout, context)

    surface = Surface(matrix_width, matrix_height)
    canvas = matrix.CreateFrameCanvas()

    running = True

    def _stop_handler(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop_handler)
    signal.signal(signal.SIGINT, _stop_handler)

    print(f"Grid display running ({matrix_width}x{matrix_height}, "
          f"{context.cols}x{context.rows} cells, {len(widgets)} widgets)")

    try:
        while running:
            frame_start = time.time()
            new_mtime = _layout_mtime()
            if new_mtime != layout_mtime:
                layout_mtime = new_mtime
                stop_widgets(widgets)
                layout = read_layout()
                context = WidgetContext(
                    settings, layout, geometry=geometry,
                    width=matrix_width, height=matrix_height,
                )
                widgets = build_widgets(layout, context)
                print(f"Grid: reloaded layout ({len(widgets)} widgets)")

            now = time.time()
            surface.clear(tuple(layout["grid"].get("backgroundColor", (0, 0, 0))))
            if layout["grid"].get("showBorders"):
                _draw_grid_borders(surface, layout, context)

            for widget in widgets:
                try:
                    widget.update(now)
                    widget.render(surface, context.widget_pixel_rect(widget.spec))
                except Exception as error:  # keep the display alive on widget bugs
                    print(f"Grid: widget {widget.id!r} failed: {error}")

            canvas.SetImage(surface.image)
            canvas = matrix.SwapOnVSync(canvas)

            remaining = FRAME_INTERVAL - (time.time() - frame_start)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        stop_widgets(widgets)
        try:
            matrix.Clear()
        except Exception:
            pass
        print("Grid display stopped")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:  # pragma: no cover - startup failures
        print(f"Grid display failed to start: {error}", file=sys.stderr)
        sys.exit(1)
