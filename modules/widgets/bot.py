# modules/widgets/bot.py
"""Grid widget that renders the display bot."""
from .base import Widget
from ..bot.motion import eye_options
from ..bot.render import draw_face
from ..bot.styles import available_styles


class BotWidget(Widget):
    type_id = "bot"

    def __init__(self, spec, context):
        super().__init__(spec, context)

        configured_style = (
            self.config.get("faceStyle")
            or context.settings.get("botFaceStyle")
            or "robot"
        )
        self.face_style = (
            configured_style
            if configured_style in available_styles()
            else "robot"
        )

        accent = (
            self.config.get("accent")
            or context.settings.get("botRobotAccent")
            or "#ffb000"
        )
        self.options = {
            "color": self.color,
            "accent": accent,
            **eye_options(context.settings, self.config),
        }

    def update(self, now):
        self.context.update_bot(now)

    def render(self, surface, rect):
        draw_face(
            surface,
            rect,
            self.context.bot_engine.model,
            style=self.face_style,
            options=self.options,
        )
