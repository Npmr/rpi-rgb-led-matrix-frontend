import unittest

from modules.bot.face import MOODS, MOOD_NAMES, Face, FaceModel, clamp
from modules.bot.render import draw_face, render_face
from modules.bot.styles import available_styles, get_style
from modules.surface import Surface


SIZES = ((32, 32), (64, 32), (64, 64), (128, 64), (256, 128))


class TestFaceModel(unittest.TestCase):

    def test_all_expected_moods_exist(self):
        for mood in (
            "idle", "happy", "excited", "curious", "thinking",
            "sad", "alarmed", "sleepy", "love", "wink",
        ):
            self.assertIn(mood, MOODS)
        self.assertEqual(tuple(MOODS), MOOD_NAMES)

    def test_unknown_mood_falls_back_to_idle(self):
        model = FaceModel(mood="does-not-exist")
        self.assertEqual(model.mood, "idle")
        self.assertFalse(model.set_mood("nope"))

    def test_mood_eases_towards_target(self):
        model = FaceModel(mood="idle")
        model.update(0.0)
        self.assertTrue(model.set_mood("happy"))
        model.update(0.05)
        self.assertLess(model.face.mouth_curve, MOODS["happy"].mouth_curve)
        for step in range(1, 41):
            model.update(step * 0.05)
        self.assertAlmostEqual(
            model.face.mouth_curve, MOODS["happy"].mouth_curve, places=2
        )

    def test_blink_closes_and_reopens_the_eyes(self):
        model = FaceModel(mood="idle", animations=False)
        model.update(0.0)
        model.blink(0.0)
        model.update(0.08)
        self.assertTrue(model.is_blinking)
        self.assertLess(model.snapshot().eye_left, 0.1)
        model.update(0.2)
        self.assertFalse(model.is_blinking)
        self.assertAlmostEqual(model.snapshot().eye_left, 1.0, places=2)

    def test_sleeping_switches_to_sleepy_and_wakes_to_idle(self):
        model = FaceModel(mood="happy")
        model.set_sleeping(True)
        self.assertTrue(model.sleeping)
        self.assertEqual(model.mood, "sleepy")
        model.set_sleeping(False)
        self.assertFalse(model.sleeping)
        self.assertEqual(model.mood, "idle")

    def test_animation_can_be_disabled(self):
        model = FaceModel(mood="idle", animations=False)
        model.update(1.2)
        self.assertEqual(model.snapshot().bob, 0.0)

    def test_bob_is_bounded(self):
        model = FaceModel(mood="idle")
        for step in range(0, 200):
            model.update(step * 0.05)
            self.assertLessEqual(abs(model.snapshot().bob), 0.55)

    def test_clamp(self):
        self.assertEqual(clamp(-2, 0, 1), 0)
        self.assertEqual(clamp(2, 0, 1), 1)


class TestFaceStyles(unittest.TestCase):

    def test_all_styles_are_registered(self):
        self.assertIn("robot", available_styles())
        self.assertIn("emoji", available_styles())
        self.assertIn("screen", available_styles())
        self.assertEqual(get_style("robot").id, "robot")
        self.assertEqual(get_style("screen").id, "screen")
        self.assertEqual(get_style("unknown").id, "robot")

    def test_eye_geometry_changes_the_face(self):
        model = FaceModel(mood="idle", animations=False)
        model.update(0.0)
        face = model.snapshot()
        for style in available_styles():
            normal = render_face(64, 64, face, style=style)
            bigger = render_face(
                64, 64, face, style=style, options={"eyeSize": 1.8}
            )
            wider = render_face(
                64, 64, face, style=style, options={"eyeGap": 1.0}
            )
            lower = render_face(
                64, 64, face, style=style, options={"eyeOffsetY": 4}
            )
            with self.subTest(style=style):
                self.assertNotEqual(normal.tobytes(), bigger.tobytes())
                self.assertNotEqual(normal.tobytes(), wider.tobytes())
                self.assertNotEqual(normal.tobytes(), lower.tobytes())

    def test_extreme_eye_options_stay_inside_the_tile(self):
        model = FaceModel(mood="idle", animations=False)
        model.update(0.0)
        face = model.snapshot()
        for style in available_styles():
            image = render_face(
                32, 32, face, style=style,
                options={"eyeSize": 1.8, "eyeGap": 1.0, "eyeOffsetY": 4},
            )
            # Corners must remain untouched: eyes never spill to the edges.
            with self.subTest(style=style):
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertEqual(image.getpixel((31, 31))[3], 0)

    def test_eye_options_are_optional(self):
        model = FaceModel(mood="idle", animations=False)
        model.update(0.0)
        face = model.snapshot()
        for style in available_styles():
            with self.subTest(style=style):
                self.assertIsNotNone(
                    render_face(32, 32, face, style=style).getbbox()
                )

    def test_every_mood_renders_in_every_style_and_size(self):
        for style in available_styles():
            for mood in MOOD_NAMES:
                model = FaceModel(mood=mood, animations=False)
                model.update(0.0)
                for width, height in SIZES:
                    with self.subTest(style=style, mood=mood, size=(width, height)):
                        image = render_face(
                            width, height, model.snapshot(), style=style
                        )
                        self.assertEqual(image.size, (width, height))
                        self.assertIsNotNone(image.getbbox())
                        # The face must stay inside the requested canvas.
                        left, top, right, bottom = image.getbbox()
                        self.assertGreaterEqual(left, 0)
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(right, width)
                        self.assertLessEqual(bottom, height)

    def test_emoji_style_is_strictly_black_and_white(self):
        for mood in MOOD_NAMES:
            model = FaceModel(mood=mood, animations=False)
            model.update(0.0)
            image = render_face(64, 64, model.snapshot(), style="emoji")
            for _count, (red, green, blue, alpha) in image.getcolors(
                maxcolors=64 * 64
            ):
                if alpha == 0:
                    continue
                with self.subTest(mood=mood, pixel=(red, green, blue)):
                    self.assertIn((red, green, blue), ((0, 0, 0), (255, 255, 255)))

    def test_screen_style_is_transparent_with_white_features_only(self):
        for mood in MOOD_NAMES:
            model = FaceModel(mood=mood, animations=False)
            model.update(0.0)
            image = render_face(64, 64, model.snapshot(), style="screen")
            colors = image.getcolors(maxcolors=64 * 64)
            visible = {
                pixel[:3] for _count, pixel in colors if pixel[3] > 0
            }
            with self.subTest(mood=mood):
                self.assertEqual(visible, {(255, 255, 255)})
                # Corners stay transparent: no disc or plate is drawn.
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertEqual(image.getpixel((63, 63))[3], 0)

    def test_robot_uses_the_configured_colour(self):
        model = FaceModel(mood="happy", animations=False)
        model.update(0.0)
        image = render_face(
            64, 64, model.snapshot(), style="robot",
            options={"color": "#ff0000", "accent": "#00ff00"},
        )
        colors = {
            pixel[:3]
            for _count, pixel in image.getcolors(maxcolors=64 * 64)
            if pixel[3] > 0
        }
        self.assertIn((255, 0, 0), colors)
        self.assertIn((0, 255, 0), colors)

    def test_unknown_colour_falls_back_instead_of_crashing(self):
        model = FaceModel(mood="idle", animations=False)
        model.update(0.0)
        image = render_face(
            32, 32, model.snapshot(), style="robot",
            options={"color": "not-a-colour", "accent": None},
        )
        self.assertIsNotNone(image.getbbox())

    def test_render_is_deterministic_for_a_fixed_time(self):
        first = FaceModel(mood="curious", seed=3)
        second = FaceModel(mood="curious", seed=3)
        for now in (0.0, 0.1, 0.25, 0.9):
            first.update(now)
            second.update(now)
        self.assertEqual(
            render_face(64, 64, first.snapshot(), style="robot").tobytes(),
            render_face(64, 64, second.snapshot(), style="robot").tobytes(),
        )

    def test_draw_face_is_clipped_to_the_rect(self):
        model = FaceModel(mood="happy", animations=False)
        model.update(0.0)
        surface = Surface(64, 64)
        draw_face(surface, (16, 16, 32, 32), model, style="emoji")
        self.assertEqual(surface.image.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(surface.image.getpixel((63, 63)), (0, 0, 0))
        self.assertEqual(surface.image.getpixel((32, 32)), (255, 255, 255))

    def test_draw_face_ignores_empty_rect(self):
        model = FaceModel(mood="idle")
        model.update(0.0)
        surface = Surface(32, 32)
        draw_face(surface, (0, 0, 0, 0), model)
        self.assertIsNone(surface.image.getbbox())

    def test_background_option_fills_the_tile(self):
        model = FaceModel(mood="idle", animations=False)
        model.update(0.0)
        image = render_face(
            32, 32, model.snapshot(), style="emoji",
            background=(0, 0, 40),
        )
        self.assertEqual(image.getpixel((0, 0)), (0, 0, 40, 255))

    def test_face_dataclass_defaults_are_sane(self):
        face = Face()
        self.assertEqual(face.eye_left, 1.0)
        self.assertEqual(face.eye_right, 1.0)
        self.assertGreater(face.mouth_width, 0)


if __name__ == "__main__":
    unittest.main()
