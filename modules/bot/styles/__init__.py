# modules/bot/styles/__init__.py
"""Registry of bot face styles."""
from .emoji import EmojiStyle
from .robot import RobotStyle
from .screen import ScreenStyle

_STYLES = {
    RobotStyle.id: RobotStyle(),
    EmojiStyle.id: EmojiStyle(),
    ScreenStyle.id: ScreenStyle(),
}

DEFAULT_STYLE = RobotStyle.id


def get_style(style_id):
    """Return a style instance, falling back to the robot face."""
    return _STYLES.get(style_id, _STYLES[DEFAULT_STYLE])


def available_styles():
    return tuple(_STYLES.keys())


def style_label(style_id):
    return get_style(style_id).label
