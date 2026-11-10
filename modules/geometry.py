# modules/geometry.py
"""Single source of truth for display geometry.

The physical panel wiring in ``settings.json`` (``widthInPixel``,
``heightInPixel``, ``chainLength``, ``parallelChains``, ``direction``) fully
determines the canvas the driver exposes. Pixel mappers can change the
*visible* size (U-mapper halves the width and doubles the height; a 90/270
rotation swaps the axes), so the grid must be derived through the same maths
the renderer/driver use instead of storing duplicate values.
"""

DEFAULT_PANEL = 32


def _int_setting(settings, key, default):
    try:
        return int(settings.get(key, default))
    except (TypeError, ValueError):
        return default


def get_base_rotation(settings):
    """Return the base rotation (degrees) for the configured direction."""
    direction = settings.get("direction")
    if direction == "horizontal":
        return 180
    if direction == "vertical":
        return 270
    if direction == "verticalTurned":
        return 90
    if direction == "horizontalTurned":
        return 0
    return 270


def get_pixel_mapper_config(settings, rotation):
    """Determine the pixel-mapper configuration based on panel layout."""
    parallel = _int_setting(settings, "parallelChains", 1)
    chain = _int_setting(settings, "chainLength", 1)

    # U-mapper requires: parallel > 1 AND chain >= 4 AND chain is even
    if parallel > 1 and chain >= 4 and chain % 2 == 0:
        return f"U-mapper;Rotate:{rotation}"
    return f"Rotate:{rotation}"


def get_matrix_dimensions(settings):
    """Raw (pre-pixel-mapper) matrix size in pixels."""
    width = _int_setting(settings, "widthInPixel", DEFAULT_PANEL) * _int_setting(
        settings, "chainLength", 1
    )
    height = _int_setting(settings, "heightInPixel", DEFAULT_PANEL) * _int_setting(
        settings, "parallelChains", 1
    )
    return width, height


def get_display_geometry(settings):
    """Return the visible geometry and derived grid for ``settings``.

    Keys:
        width, height   - visible canvas size after pixel mappers
        rawWidth, rawHeight - size before pixel mappers
        cellW, cellH    - pixel size of one grid cell (one panel)
        cols, rows      - number of grid cells
        rotation        - base rotation in degrees
        pixelMapper     - mapper string passed to the driver
    """
    panel_w = _int_setting(settings, "widthInPixel", DEFAULT_PANEL)
    panel_h = _int_setting(settings, "heightInPixel", DEFAULT_PANEL)
    rotation = get_base_rotation(settings) % 360
    pixel_mapper = get_pixel_mapper_config(settings, rotation)

    raw_w, raw_h = get_matrix_dimensions(settings)
    width, height = raw_w, raw_h

    # U-mapper: visible_width = (matrix_width / 64) * 32, visible_height = 2 * h
    if "U-mapper" in pixel_mapper:
        width = (width // 64) * 32
        height = 2 * height

    # Rotate mapper: 90/270 swap the axes.
    if rotation in (90, 270):
        width, height = height, width

    cell_w, cell_h = panel_w, panel_h
    if rotation in (90, 270):
        cell_w, cell_h = cell_h, cell_w

    cols = max(1, width // max(1, cell_w))
    rows = max(1, height // max(1, cell_h))

    return {
        "width": width,
        "height": height,
        "rawWidth": raw_w,
        "rawHeight": raw_h,
        "cellW": cell_w,
        "cellH": cell_h,
        "cols": cols,
        "rows": rows,
        "rotation": rotation,
        "pixelMapper": pixel_mapper,
    }
