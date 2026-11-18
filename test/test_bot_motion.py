import tempfile
import unittest
from unittest.mock import patch

from modules.bot.motion import (
    MAX_WANDER_SCALE,
    Wanderer,
    eye_options,
    face_scale,
    wander_enabled,
    wander_speed,
)
from modules.bot.status import read_status, write_status


class TestEyeOptions(unittest.TestCase):

    def test_defaults_are_neutral(self):
        options = eye_options({})
        self.assertEqual(options["eyeSize"], 1.0)
        self.assertEqual(options["eyeGap"], 0.0)
        self.assertEqual(options["eyeOffsetY"], 0.0)

    def test_settings_are_read(self):
        options = eye_options({
            "botEyeSize": 1.4,
            "botEyeGap": 0.5,
            "botEyeOffsetY": -2,
        })
        self.assertAlmostEqual(options["eyeSize"], 1.4)
        self.assertAlmostEqual(options["eyeGap"], 0.5)
        self.assertAlmostEqual(options["eyeOffsetY"], -2.0)

    def test_widget_config_wins_over_settings(self):
        options = eye_options(
            {"botEyeSize": 1.4}, {"eyeSize": 0.7, "eyeGap": 0.4}
        )
        self.assertAlmostEqual(options["eyeSize"], 0.7)
        self.assertAlmostEqual(options["eyeGap"], 0.4)

    def test_values_are_clamped(self):
        options = eye_options({
            "botEyeSize": 99,
            "botEyeGap": -99,
            "botEyeOffsetY": 99,
        })
        self.assertEqual(options["eyeSize"], 1.8)
        self.assertEqual(options["eyeGap"], -0.6)
        self.assertEqual(options["eyeOffsetY"], 4.0)

    def test_bad_values_fall_back(self):
        options = eye_options({"botEyeSize": "huge"})
        self.assertEqual(options["eyeSize"], 1.0)


class TestMotionSettings(unittest.TestCase):

    def test_face_scale_defaults_and_clamping(self):
        self.assertAlmostEqual(face_scale({}), 0.9)
        self.assertAlmostEqual(face_scale({"botFaceScale": 0.4}), 0.4)
        self.assertAlmostEqual(face_scale({"botFaceScale": 5}), 1.0)
        self.assertAlmostEqual(face_scale({"botFaceScale": "x"}), 0.9)

    def test_wander_settings(self):
        self.assertFalse(wander_enabled({}))
        self.assertTrue(wander_enabled({"botWanderEnabled": "on"}))
        self.assertTrue(wander_enabled({"botWanderEnabled": True}))
        self.assertAlmostEqual(wander_speed({}), 10.0)
        self.assertAlmostEqual(wander_speed({"botWanderSpeed": 500}), 120.0)


class TestWanderer(unittest.TestCase):

    def test_face_size_follows_the_short_side(self):
        wanderer = Wanderer(scale=0.5)
        self.assertEqual(wanderer.face_size(128, 64), (32, 32))
        self.assertEqual(wanderer.face_size(64, 128), (32, 32))

    def test_wander_scale_is_capped_so_it_can_move(self):
        wanderer = Wanderer(scale=1.0)
        self.assertLessEqual(wanderer.scale, MAX_WANDER_SCALE)

    def test_face_starts_centred(self):
        wanderer = Wanderer(scale=0.5)
        x, y, w, h = wanderer.update(0.0, 128, 64)
        self.assertEqual((w, h), (32, 32))
        self.assertEqual((x, y), (48, 16))

    def test_face_moves_over_time(self):
        wanderer = Wanderer(scale=0.5, speed=40.0, seed=3)
        start = wanderer.update(0.0, 192, 128)
        later = wanderer.update(1.0, 192, 128)
        self.assertNotEqual(start, later)

    def test_face_stays_inside_the_panel(self):
        wanderer = Wanderer(scale=0.5, speed=120.0, seed=11)
        for step in range(200):
            x, y, w, h = wanderer.update(step * 0.2, 192, 128)
            with self.subTest(step=step):
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + w, 192)
                self.assertLessEqual(y + h, 128)

    def test_pause_freezes_the_position(self):
        wanderer = Wanderer(scale=0.5, speed=40.0, seed=5)
        wanderer.update(0.0, 192, 128)
        before = wanderer.update(0.5, 192, 128)
        paused = wanderer.update(1.0, 192, 128, paused=True)
        self.assertEqual(before, paused)
        # A long pause must not teleport the face when it resumes.
        after = wanderer.update(1.1, 192, 128, paused=True)
        self.assertEqual(paused, after)

    def test_resize_keeps_the_face_in_bounds(self):
        wanderer = Wanderer(scale=0.5, speed=40.0, seed=9)
        for step in range(20):
            wanderer.update(step * 0.5, 192, 128)
        x, y, w, h = wanderer.update(10.0, 64, 64)
        self.assertLessEqual(x + w, 64)
        self.assertLessEqual(y + h, 64)

    def test_no_free_space_keeps_the_face_still(self):
        wanderer = Wanderer(scale=1.0)
        # The cap still leaves a little room, so use a tiny panel.
        first = wanderer.update(0.0, 12, 12)
        second = wanderer.update(5.0, 12, 12)
        self.assertEqual(first, second)


class TestBotStatus(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        import os

        self.path = os.path.join(self._tmp.name, "state.json")
        self._env = patch.dict(os.environ, {"BOT_STATUS_PATH": self.path})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_roundtrip(self):
        write_status({"mood": "happy", "mode": "fullscreen"})
        status = read_status()
        self.assertEqual(status["mood"], "happy")
        self.assertEqual(status["mode"], "fullscreen")
        self.assertIn("updatedAt", status)

    def test_missing_or_broken_file_returns_empty(self):
        self.assertEqual(read_status(), {})
        with open(self.path, "w") as handle:
            handle.write("{broken")
        self.assertEqual(read_status(), {})

    def test_stale_status_is_ignored(self):
        write_status({"mood": "happy"})
        self.assertEqual(read_status(max_age=-1), {})


if __name__ == "__main__":
    unittest.main()
