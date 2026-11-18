import os
import tempfile
import unittest
from unittest.mock import patch

from modules.bot.bus import BotBus
from modules.bot.face import MOODS
from modules.layout_handler import default_layout
from modules.surface import Surface
from modules.widgets import WidgetContext
from modules.widgets.bot import BotWidget


def spec(config=None, style=None, w=1, h=1):
    return {
        "id": "bot",
        "type": "bot",
        "col": 0,
        "row": 0,
        "w": w,
        "h": h,
        "style": style or {"color": [0, 212, 255]},
        "config": config or {},
    }


class TestBotWidget(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._env = patch.dict(os.environ, {"BOT_EVENTS_DIR": self._tmp.name})
        self._env.start()
        self.addCleanup(self._env.stop)

    def context(self, settings=None):
        settings = dict(settings or {})
        settings.setdefault("timezone", "UTC")
        settings.setdefault("botSleepEnabled", "off")
        return WidgetContext(settings, default_layout(), width=64, height=32)

    def render(self, widget, size=32):
        surface = Surface(size, size)
        widget.render(surface, (0, 0, size, size))
        return surface.image

    def test_every_style_renders_something(self):
        for style_id in ("robot", "emoji", "screen"):
            widget = BotWidget(spec({"faceStyle": style_id}), self.context())
            image = self.render(widget)
            with self.subTest(style=style_id):
                self.assertEqual(image.size, (32, 32))
                self.assertIsNotNone(image.getbbox())

    def test_unknown_style_falls_back_to_robot(self):
        widget = BotWidget(spec({"faceStyle": "does-not-exist"}), self.context())
        self.assertEqual(widget.face_style, "robot")

    def test_face_style_comes_from_settings_when_not_configured(self):
        context = self.context({"botFaceStyle": "emoji"})
        widget = BotWidget(spec(), context)
        self.assertEqual(widget.face_style, "emoji")

    def test_widget_config_wins_over_settings(self):
        context = self.context({"botFaceStyle": "emoji"})
        widget = BotWidget(spec({"faceStyle": "screen"}), context)
        self.assertEqual(widget.face_style, "screen")

    def test_accent_uses_config_then_settings_then_default(self):
        context = self.context({"botRobotAccent": "#123456"})
        self.assertEqual(
            BotWidget(spec({"accent": "#abcdef"}), context).options["accent"],
            "#abcdef",
        )
        self.assertEqual(
            BotWidget(spec(), context).options["accent"], "#123456"
        )
        self.assertEqual(
            BotWidget(spec(), self.context()).options["accent"], "#ffb000"
        )

    def test_widgets_share_one_engine_and_update_once_per_frame(self):
        context = self.context()
        first = BotWidget(spec(), context)
        second = BotWidget(spec(), context)

        self.assertIs(first.context.bot_engine, second.context.bot_engine)

        with patch.object(context.bot_engine, "update") as update:
            first.update(100.0)
            second.update(100.0)
            self.assertEqual(update.call_count, 1)

            first.update(100.1)
            self.assertEqual(update.call_count, 2)

    def test_event_changes_the_rendered_face(self):
        context = self.context()
        widget = BotWidget(spec({"faceStyle": "screen"}), context)

        idle = self.render(widget).tobytes()

        BotBus(directory=self._tmp.name).publish(
            {"type": "alarm"}, source="test", now=100.0
        )
        widget.update(100.0)
        scared = self.render(widget).tobytes()

        self.assertNotEqual(idle, scared)
        self.assertEqual(context.bot_engine.state()["mood"], "alarmed")
        self.assertIn("alarmed", MOODS)

    def test_render_is_clipped_to_the_widget_rect(self):
        context = self.context()
        widget = BotWidget(spec(), context)
        surface = Surface(64, 32)
        widget.render(surface, (0, 0, 32, 32))

        left = surface.image.crop((0, 0, 32, 32)).tobytes()
        right = surface.image.crop((32, 0, 64, 32)).tobytes()
        self.assertNotEqual(left, right)


if __name__ == "__main__":
    unittest.main()
