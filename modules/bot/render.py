# modules/bot/render.py
"""Render a bot expression onto a surface or a standalone image."""
from .face import FaceModel
from .styles import DEFAULT_STYLE, available_styles, get_style


def render_face(width, height, face, style=DEFAULT_STYLE, options=None,
                background=None):
    """Render one expression to an RGBA image of ``width`` x ``height``."""
    style_impl = get_style(style)
    return style_impl.render(
        max(1, int(width)),
        max(1, int(height)),
        face,
        options=options,
        background=background,
    )


def draw_face(surface, rect, model, style=DEFAULT_STYLE, options=None,
              background=None):
    """Render ``model`` into ``surface`` at ``rect`` = (x, y, w, h)."""
    x, y, width, height = (int(value) for value in rect)
    if width <= 0 or height <= 0:
        return
    image = render_face(
        width, height, model.snapshot(), style=style,
        options=options, background=background,
    )
    surface.image.paste(image, (x, y), image)


__all__ = ["render_face", "draw_face", "FaceModel", "available_styles"]
