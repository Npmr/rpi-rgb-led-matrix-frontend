import unittest
from unittest.mock import patch

import bot_display
from modules.bot.motion import Wanderer


class TestFaceRect(unittest.TestCase):

    def test_no_wander_centres_the_face(self):
        settings = {"botFaceScale": 0.5}
        rect = bot_display._face_rect(0.0, 64, 64, settings, None)
        self.assertEqual(rect, (16, 16, 32, 32))

    def test_wide_panel_uses_the_short_side(self):
        settings = {"botFaceScale": 0.5}
        rect = bot_display._face_rect(0.0, 128, 64, settings, None)
        self.assertEqual(rect, (48, 16, 32, 32))

    def test_wander_uses_the_wanderer(self):
        settings = {"botFaceScale": 0.5, "botWanderEnabled": "on"}
        wanderer = Wanderer(scale=0.5, seed=2)
        rect = bot_display._face_rect(0.0, 128, 64, settings, wanderer)
        self.assertEqual(rect[2:], (32, 32))

    def test_wander_without_a_wanderer_still_centres(self):
        settings = {"botFaceScale": 0.5, "botWanderEnabled": "on"}
        rect = bot_display._face_rect(0.0, 64, 64, settings, None)
        self.assertEqual(rect, (16, 16, 32, 32))

    def test_scale_is_clamped(self):
        rect = bot_display._face_rect(0.0, 64, 64, {"botFaceScale": 9}, None)
        self.assertEqual(rect[2], 64)


class TestRendererOptions(unittest.TestCase):

    def test_default_options(self):
        options = bot_display._options({})
        self.assertEqual(options["color"], "#00d4ff")
        self.assertEqual(options["accent"], "#ffb000")
        self.assertEqual(options["eyeSize"], 1.0)

    def test_settings_override_options(self):
        options = bot_display._options({
            "botFaceColor": "#112233",
            "botRobotAccent": "#445566",
            "botEyeSize": 1.5,
        })
        self.assertEqual(options["color"], "#112233")
        self.assertEqual(options["accent"], "#445566")
        self.assertAlmostEqual(options["eyeSize"], 1.5)

    def test_style_falls_back_to_robot(self):
        self.assertEqual(bot_display._face_style({}), "robot")
        self.assertEqual(
            bot_display._face_style({"botFaceStyle": "emoji"}), "emoji"
        )
        self.assertEqual(
            bot_display._face_style({"botFaceStyle": "made-up"}), "robot"
        )

    def test_config_style_wins(self):
        self.assertEqual(
            bot_display._face_style({"botFaceStyle": "emoji"},
                                   {"faceStyle": "screen"}),
            "screen",
        )

    def test_background_colour(self):
        self.assertEqual(
            bot_display._color_setting({"botBackground": "#101010"},
                                       "botBackground", "#000000"),
            "#101010",
        )
        self.assertEqual(
            bot_display._color_setting({}, "botBackground", "#000000"),
            "#000000",
        )


if __name__ == "__main__":
    unittest.main()
