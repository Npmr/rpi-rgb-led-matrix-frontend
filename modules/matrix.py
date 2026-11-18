# modules/matrix.py
"""Shared RGB matrix construction for the Pillow-based renderers.

``grid_display.py`` and the full-screen bot renderer must create the matrix
with identical options; keeping that in one module prevents the two from
drifting apart.
"""

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:  # pragma: no cover - hardware dependency
    RGBMatrix = None
    RGBMatrixOptions = None

from .geometry import get_base_rotation, get_pixel_mapper_config


def _int_setting(settings, key, default):
    try:
        return int(settings.get(key, default))
    except (TypeError, ValueError):
        return default


def build_matrix(settings):
    """Create the RGBMatrix using the same options as the CLI viewers."""
    if RGBMatrix is None:
        raise RuntimeError(
            "The rgbmatrix Python bindings are not installed. Install them from "
            "the rpi-rgb-led-matrix repository root with: "
            "sudo pip3 install --break-system-packages ."
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
