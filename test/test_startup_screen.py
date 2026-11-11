import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from PIL import Image

from modules import startup_screen as ss
from modules.surface import Surface, load_font


SETTINGS = {
    'heightInPixel': '32',
    'widthInPixel': '32',
    'chainLength': '12',
    'parallelChains': '2',
    'direction': 'horizontal',
    'deviceName': 'Pixel Matrix',
    'startupScreenEnabled': 'on',
    'startupScreenImage': '',
    'startupScreenText': 'Welcome home',
    'startupScreenDuration': '30',
}


class StartupScreenTestCase(unittest.TestCase):

    def setUp(self):
        ss.reset_startup_screen_state()

    def tearDown(self):
        ss.reset_startup_screen_state()


class TestComputeLocalIp(unittest.TestCase):

    def test_returns_a_string(self):
        address = ss.compute_local_ip()
        self.assertIsInstance(address, str)
        self.assertTrue(address)

    def test_falls_back_to_hostname_lookup(self):
        with patch('modules.startup_screen.socket.socket') as mock_socket:
            mock_socket.return_value.connect.side_effect = OSError('offline')
            with patch('modules.startup_screen.socket.gethostbyname',
                       return_value='192.168.1.5'):
                self.assertEqual(ss.compute_local_ip(), '192.168.1.5')

    def test_offline_returns_placeholder(self):
        with patch('modules.startup_screen.socket.socket') as mock_socket, \
                patch('modules.startup_screen.socket.gethostbyname',
                      side_effect=OSError('no dns')):
            mock_socket.return_value.connect.side_effect = OSError('offline')
            self.assertEqual(ss.compute_local_ip(), 'offline')


class TestInfoImage(StartupScreenTestCase):

    def test_renders_at_visible_canvas_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'info.png')
            result = ss.render_info_image(dict(SETTINGS), ip='10.0.0.2',
                                          path=path)
            self.assertEqual(result, path)
            with Image.open(path) as img:
                self.assertEqual(img.size, (192, 128))
                self.assertGreater(img.convert('L').getextrema()[1], 0)

    def test_explicit_size_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'info.png')
            ss.render_info_image(dict(SETTINGS), ip='10.0.0.2',
                                 size=(64, 32), path=path)
            with Image.open(path) as img:
                self.assertEqual(img.size, (64, 32))

    def test_lines_contain_ip_and_message(self):
        lines = ss.build_info_lines(dict(SETTINGS), '10.0.0.2', 192, 128)
        joined = ' '.join(lines)
        self.assertIn('IP: 10.0.0.2', joined)
        self.assertIn('Welcome', joined)
        self.assertIn('Pixel Matrix', joined)

    def test_long_message_is_wrapped_and_bounded(self):
        settings = dict(SETTINGS, startupScreenText='word ' * 200)
        plan = ss.plan_info(settings, '10.0.0.2', 192, 128)
        self.assertGreater(len(plan['lines']), 2)
        # Too much text for the canvas: the caller switches to a ticker.
        self.assertFalse(plan['fits'])

    def test_long_words_are_split_by_character(self):
        settings = dict(SETTINGS, deviceName='', startupScreenText='')
        lines = ss.build_info_lines(settings, '192.168.100.200', 32, 32)
        self.assertGreater(len(lines), 1)
        surface = Surface(32, 32)
        font = load_font(6)
        for line in lines:
            self.assertLessEqual(surface.measure_text(line, font), 28)

    def test_device_name_is_wrapped_too(self):
        settings = dict(SETTINGS, deviceName='Pixel Matrix Deluxe')
        plan = ss.plan_info(settings, '10.0.0.2', 64, 32)
        joined = ' '.join(plan['lines'])
        self.assertIn('Pixel', joined)
        self.assertIn('Deluxe', joined)

    def test_missing_message_still_shows_ip(self):
        settings = dict(SETTINGS, startupScreenText='')
        lines = ss.build_info_lines(settings, '10.0.0.2', 192, 128)
        self.assertIn('IP: 10.0.0.2', lines)

    def test_large_canvas_uses_the_largest_font_that_fits(self):
        plan = ss.plan_info(dict(SETTINGS), '10.0.0.2', 192, 128)
        self.assertTrue(plan['fits'])
        self.assertEqual(plan['fontHeight'], 20)
        self.assertEqual(plan['headerLines'], 2)

    def test_small_canvas_does_not_fit(self):
        # A 32x32 panel cannot show name, IP and message without scrolling.
        plan = ss.plan_info(dict(SETTINGS), '192.168.1.123', 32, 32)
        self.assertFalse(plan['fits'])


class TestInfoTicker(StartupScreenTestCase):

    def test_small_canvas_renders_a_looping_gif(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'startup.gif')
            result = ss.render_info_image(dict(SETTINGS), ip='192.168.1.123',
                                          size=(32, 32), path=path)
            self.assertTrue(result.endswith('.gif'))
            with Image.open(result) as img:
                self.assertEqual(img.format, 'GIF')
                self.assertEqual(img.size, (32, 32))
                self.assertGreater(img.n_frames, 1)
                self.assertEqual(img.info.get('loop'), 0)

    def test_ticker_always_mode_on_a_large_canvas(self):
        settings = dict(SETTINGS, startupScreenScroll='always')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'startup.gif')
            result = ss.render_info_image(settings, ip='10.0.0.2',
                                          size=(192, 128), path=path)
            self.assertTrue(result.endswith('.gif'))

    def test_scroll_never_keeps_the_static_png(self):
        settings = dict(SETTINGS, startupScreenScroll='never')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'startup.png')
            result = ss.render_info_image(settings, ip='192.168.1.123',
                                          size=(32, 32), path=path)
            self.assertTrue(result.endswith('.png'))
            with Image.open(result) as img:
                self.assertEqual(img.format, 'PNG')
                self.assertEqual(img.size, (32, 32))

    def test_ticker_frames_scroll(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'startup.gif')
            ss.render_info_image(dict(SETTINGS), ip='192.168.1.123',
                                  size=(32, 32), path=path)
            with Image.open(path) as img:
                img.seek(4)
                first = img.convert('L').tobytes()
                img.seek(40)
                later = img.convert('L').tobytes()
        self.assertNotEqual(first, later)

    def test_explicit_font_size_is_respected(self):
        settings = dict(SETTINGS, startupScreenFontSize='13')
        plan = ss.plan_info(settings, '10.0.0.2', 192, 128)
        self.assertEqual(plan['fontHeight'], 13)
        self.assertTrue(plan['fits'])

    def test_invalid_font_size_falls_back_to_auto(self):
        self.assertIsNone(ss.font_size_setting(
            {'startupScreenFontSize': 'huge'}))
        self.assertIsNone(ss.font_size_setting({'startupScreenFontSize': '1'}))
        self.assertEqual(ss.font_size_setting(
            {'startupScreenFontSize': '13'}), 13)
        self.assertIsNone(ss.font_size_setting({}))

    def test_ticker_font_grows_with_the_canvas(self):
        self.assertEqual(ss.ticker_font_height({}, 32, 32), 8)
        self.assertEqual(ss.ticker_font_height({}, 128, 192), 20)

    def test_scroll_mode_and_speed_are_sanitised(self):
        self.assertEqual(ss.scroll_mode({'startupScreenScroll': 'always'}),
                         'always')
        self.assertEqual(ss.scroll_mode({'startupScreenScroll': 'nope'}),
                         'auto')
        self.assertEqual(ss.scroll_mode({}), 'auto')
        self.assertEqual(ss.scroll_speed_setting(
            {'startupScreenScrollSpeed': '0'}), 1.0)
        self.assertEqual(ss.scroll_speed_setting(
            {'startupScreenScrollSpeed': '999'}), float(ss.MAX_SCROLL_SPEED))
        self.assertEqual(ss.scroll_speed_setting({}),
                         float(ss.DEFAULT_SCROLL_SPEED))


class TestDurationSetting(unittest.TestCase):

    def test_uses_value(self):
        self.assertEqual(ss.duration_setting({'startupScreenDuration': '15'}), 15)

    def test_zero_means_until_dismissed(self):
        self.assertEqual(ss.duration_setting({'startupScreenDuration': '0'}), 0)

    def test_invalid_falls_back_to_default(self):
        self.assertEqual(
            ss.duration_setting({'startupScreenDuration': 'abc'}),
            ss.DEFAULT_DURATION)
        self.assertEqual(
            ss.duration_setting({}), ss.DEFAULT_DURATION)

    def test_negative_is_clamped(self):
        self.assertEqual(ss.duration_setting({'startupScreenDuration': '-5'}), 0)


class TestShowStartupScreen(StartupScreenTestCase):

    @patch('modules.startup_screen.Timer')
    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    @patch('modules.startup_screen.render_info_image', return_value='/tmp/info.png')
    def test_shows_generated_info_screen(self, mock_render, mock_display,
                                         mock_grid, mock_timer):
        self.assertTrue(ss.show_startup_screen(dict(SETTINGS)))
        mock_render.assert_called_once()
        mock_display.assert_called_once_with('/tmp/info.png',
                                             cleanup_path='/tmp/info.png')
        mock_timer.assert_called_once()
        self.assertEqual(mock_timer.call_args[0][0], 30)
        mock_timer.return_value.start.assert_called_once()

    @patch('modules.startup_screen.Timer')
    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    @patch('modules.startup_screen.process_image_for_display',
           return_value='/tmp/picture.png')
    @patch('modules.startup_screen._startup_image_path',
           return_value='/static/pictures/a.png')
    def test_shows_configured_picture(self, mock_path, mock_process,
                                      mock_display, mock_grid, mock_timer):
        settings = dict(SETTINGS, startupScreenImage='a.png')
        self.assertTrue(ss.show_startup_screen(settings))
        mock_process.assert_called_once()
        mock_display.assert_called_once_with('/tmp/picture.png',
                                             cleanup_path='/tmp/picture.png')

    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    def test_disabled_is_a_no_op(self, mock_display, mock_grid):
        settings = dict(SETTINGS, startupScreenEnabled='')
        self.assertFalse(ss.show_startup_screen(settings))
        mock_display.assert_not_called()

    @patch('modules.startup_screen.is_grid_running', return_value=True)
    @patch('modules.startup_screen.display_image_file')
    def test_grid_running_is_a_no_op(self, mock_display, mock_grid):
        self.assertFalse(ss.show_startup_screen(dict(SETTINGS)))
        mock_display.assert_not_called()

    @patch('modules.startup_screen.Timer')
    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    @patch('modules.startup_screen.render_info_image', return_value='/tmp/info.png')
    def test_only_shows_once(self, mock_render, mock_display, mock_grid,
                             mock_timer):
        self.assertTrue(ss.show_startup_screen(dict(SETTINGS)))
        self.assertFalse(ss.show_startup_screen(dict(SETTINGS)))
        self.assertEqual(mock_display.call_count, 1)

    @patch('modules.startup_screen.Timer')
    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    @patch('modules.startup_screen.render_info_image', return_value='/tmp/info.png')
    def test_duration_zero_has_no_timer(self, mock_render, mock_display,
                                        mock_grid, mock_timer):
        settings = dict(SETTINGS, startupScreenDuration='0')
        self.assertTrue(ss.show_startup_screen(settings))
        mock_timer.assert_not_called()

    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file',
           side_effect=OSError('boom'))
    @patch('modules.startup_screen.render_info_image', return_value='/tmp/info.png')
    def test_display_failure_is_reported_not_raised(self, mock_render,
                                                    mock_display, mock_grid):
        self.assertFalse(ss.show_startup_screen(dict(SETTINGS)))


class TestCancelStartupScreen(StartupScreenTestCase):

    @patch('modules.startup_screen.Timer')
    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    @patch('modules.startup_screen.render_info_image', return_value='/tmp/info.png')
    def test_cancel_stops_timer_and_blocks_future_shows(self, mock_render,
                                                        mock_display,
                                                        mock_grid, mock_timer):
        self.assertTrue(ss.show_startup_screen(dict(SETTINGS)))
        timer = mock_timer.return_value
        ss.cancel_startup_screen()
        timer.cancel.assert_called_once()
        mock_display.reset_mock()
        self.assertFalse(ss.show_startup_screen(dict(SETTINGS)))
        mock_display.assert_not_called()

    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    @patch('modules.startup_screen.render_info_image', return_value='/tmp/info.png')
    def test_cancel_while_launching_is_ignored(self, mock_render, mock_display,
                                               mock_grid):
        # display_image_file() calls stopProcess() -> cancel_startup_screen();
        # that must not cancel the screen we are currently starting.
        def fake_display(*args, **kwargs):
            ss.cancel_startup_screen()
            self.assertFalse(ss._cancelled)

        mock_display.side_effect = fake_display
        self.assertTrue(ss.show_startup_screen(dict(SETTINGS)))

    def test_timeout_ignores_when_not_showing(self):
        ss._showing = False
        with patch('modules.display_control.stopProcess') as mock_stop:
            ss._on_timeout()
        mock_stop.assert_not_called()


class TestTimeoutStopsDisplay(StartupScreenTestCase):

    @patch('modules.startup_screen.render_blank_image', return_value='/tmp/black.png')
    @patch('modules.display_control.display_image_file')
    @patch('modules.startup_screen.Timer')
    @patch('modules.startup_screen.is_grid_running', return_value=False)
    @patch('modules.startup_screen.display_image_file')
    @patch('modules.startup_screen.render_info_image', return_value='/tmp/info.png')
    def test_timer_callback_stops_the_process(self, mock_render, mock_display,
                                              mock_grid, mock_timer,
                                              mock_blank_display, mock_blank):
        self.assertTrue(ss.show_startup_screen(dict(SETTINGS)))
        callback = mock_timer.call_args[0][1]
        mock_display.reset_mock()
        with patch('modules.display_control.stopProcess') as mock_stop:
            callback()
        mock_stop.assert_called_once()
        # The display is blanked instead of freezing the startup image.
        mock_blank.assert_called_once()
        mock_blank_display.assert_called_once_with('/tmp/black.png',
                                                   cleanup_path='/tmp/black.png')

    def test_blank_image_matches_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'blank.png')
            ss.render_blank_image(dict(SETTINGS), path=path)
            with Image.open(path) as img:
                self.assertEqual(img.size, (192, 128))
                self.assertEqual(img.convert('L').getextrema(), (0, 0))


class TestStopProcessCancels(StartupScreenTestCase):

    def test_display_action_cancels_startup_screen(self):
        from modules import display_control

        ss._showing = True
        with patch.object(display_control, 'stop_grid_display'), \
                patch.object(display_control.psutil, 'process_iter',
                             return_value=[]), \
                patch.object(display_control.immich_controller,
                             'stop_immich_loop'):
            display_control.stopProcess()
        self.assertTrue(ss._cancelled)
        self.assertFalse(ss._showing)


class TestScheduleStartupScreen(StartupScreenTestCase):

    @patch('modules.startup_screen.show_startup_screen')
    @patch('modules.startup_screen.Timer')
    def test_schedules_in_background(self, mock_timer, mock_show):
        timer = mock_timer.return_value
        ss.schedule_startup_screen(delay=1.5)
        mock_timer.assert_called_once()
        self.assertEqual(mock_timer.call_args[0][0], 1.5)
        timer.start.assert_called_once()
        # Run the callback the way the timer would.
        mock_timer.call_args[0][1]()
        mock_show.assert_called_once()


if __name__ == '__main__':
    unittest.main()
