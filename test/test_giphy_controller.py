"""Tests for the Giphy slideshow loop.

The bug these cover: pressing Stop killed the current picture, but the loop
thread kept sleeping and displayed another GIF minutes later, so the display
appeared to start itself again.
"""
import os
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from modules import giphy_controller as gc


class GiphyTestCase(unittest.TestCase):

    def setUp(self):
        self._reset()
        self.addCleanup(self._reset)

    def _reset(self):
        gc.giphy_running = False
        gc._current_search_term = None
        gc._giphy_thread = None
        gc._stop_event.clear()

    def _fast_wait(self):
        """Replace the interruptible wait with a very short one."""
        return patch.object(
            gc, '_wait',
            side_effect=lambda seconds: gc._stop_event.wait(0.01))

    def _join(self, timeout=5.0):
        thread = gc._giphy_thread
        if thread is not None:
            thread.join(timeout)
            self.assertFalse(thread.is_alive(),
                             'the Giphy loop thread did not stop')


class TestStopGiphyLoop(GiphyTestCase):

    def test_stop_returns_true_only_when_running(self):
        self.assertFalse(gc.stop_giphy_loop())
        gc.giphy_running = True
        self.assertTrue(gc.stop_giphy_loop())
        self.assertFalse(gc.giphy_running)

    def test_stop_sets_the_event_so_a_waiting_loop_wakes_up(self):
        gc.giphy_running = True
        gc._current_search_term = 'art'
        gc.stop_giphy_loop()
        self.assertTrue(gc._stop_event.is_set())
        self.assertIsNone(gc._current_search_term)

    def test_start_clears_the_stop_event(self):
        gc.stop_giphy_loop()
        self.assertTrue(gc._stop_event.is_set())
        with patch.object(gc.threading, 'Thread'):
            gc.start_giphy_loop('art')
        self.assertFalse(gc._stop_event.is_set())
        self.assertTrue(gc.giphy_running)
        self.assertEqual(gc._current_search_term, 'art')

    def test_second_start_does_not_spawn_another_thread(self):
        with patch.object(gc.threading, 'Thread') as mock_thread:
            gc.start_giphy_loop()
            gc.start_giphy_loop()
        self.assertEqual(mock_thread.call_count, 1)

    def test_start_and_stop_publish_the_switch_state(self):
        callback = MagicMock()
        gc.set_mqtt_publish_callback(callback)
        self.addCleanup(gc.set_mqtt_publish_callback, None)
        with patch.object(gc.threading, 'Thread'):
            gc.start_giphy_loop()
            gc.stop_giphy_loop()
        payloads = [call[0][1] for call in callback.call_args_list]
        self.assertEqual(payloads, ['on', 'off'])
        self.assertTrue(all('giphy_control/state' in call[0][0]
                            for call in callback.call_args_list))


class TestGiphyLoopStops(GiphyTestCase):

    def _touch(self, name='loop-test.gif'):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, name)
        with open(path, 'w') as handle:
            handle.write('x')
        return path

    def test_loop_shows_one_picture_then_exits_on_stop(self):
        gif_path = self._touch()
        shown = []

        def fake_display(*args, **kwargs):
            shown.append(args[0])
            # The user presses Stop while the picture is on the panel.
            gc.stop_giphy_loop()

        with patch.object(gc.giphy_handler, 'fetch_trending_gif',
                          return_value='http://example.test/a.gif'), \
                patch.object(gc.giphy_handler, 'download_gif',
                             return_value=gif_path), \
                patch.object(gc.display_control, 'process_image_async',
                             side_effect=fake_display), \
                self._fast_wait():
            gc.start_giphy_loop()
            self._join()

        self.assertEqual(len(shown), 1,
                         'the loop showed another picture after the stop')
        self.assertFalse(gc.giphy_running)

    def test_stop_during_fetch_shows_nothing(self):
        def fetch_and_stop():
            gc.stop_giphy_loop()
            return 'http://example.test/b.gif'

        with patch.object(gc.giphy_handler, 'fetch_trending_gif',
                          side_effect=fetch_and_stop), \
                patch.object(gc.giphy_handler, 'download_gif') as mock_download, \
                patch.object(gc.display_control,
                             'process_image_async') as mock_display, \
                self._fast_wait():
            gc.start_giphy_loop()
            self._join()

        mock_download.assert_not_called()
        mock_display.assert_not_called()

    def test_stop_during_download_shows_nothing_and_cleans_up(self):
        gif_path = self._touch('downloaded.gif')

        def download_and_stop(_url):
            gc.stop_giphy_loop()
            return gif_path

        with patch.object(gc.giphy_handler, 'fetch_trending_gif',
                          return_value='http://example.test/c.gif'), \
                patch.object(gc.giphy_handler, 'download_gif',
                             side_effect=download_and_stop), \
                patch.object(gc.display_control,
                             'process_image_async') as mock_display, \
                self._fast_wait():
            gc.start_giphy_loop()
            self._join()

        mock_display.assert_not_called()
        self.assertFalse(os.path.exists(gif_path))

    def test_a_stale_generation_cannot_keep_a_new_run_alive(self):
        gc.giphy_running = True
        gc._loop_generation = 5
        with patch.object(gc.giphy_handler, 'fetch_trending_gif') as mock_fetch:
            gc.giphy_display_loop(generation=4)
        mock_fetch.assert_not_called()

    def test_loop_thread_is_current_only_inside_the_thread(self):
        self.assertFalse(gc.loop_thread_is_current())
        seen = {}

        def check():
            seen['inside'] = gc.loop_thread_is_current()

        thread = threading.Thread(target=check)
        gc._giphy_thread = thread
        thread.start()
        thread.join()
        self.assertTrue(seen['inside'])
        self.assertFalse(gc.loop_thread_is_current())


if __name__ == '__main__':
    unittest.main()
