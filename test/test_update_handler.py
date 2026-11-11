import unittest
from unittest.mock import patch, MagicMock
import json
import os

from modules.update_handler import (
    trigger_update, fetch_update_info, update_script_path, is_update_running
)


class TestUpdateHandler(unittest.TestCase):

    def tearDown(self):
        # Make sure a failing test cannot leave the guard switched on.
        import modules.update_handler as handler
        handler._update_running = False

    @patch('modules.update_handler.subprocess.run')
    def test_trigger_update_default_branch(self, mock_run):
        result = trigger_update()
        self.assertEqual(result, "Update triggered successfully!")
        mock_run.assert_called_once_with(
            ['sh', update_script_path(), 'main'])

    @patch('modules.update_handler.subprocess.run')
    def test_trigger_update_custom_branch(self, mock_run):
        result = trigger_update(branch="develop")
        self.assertEqual(result, "Update triggered successfully!")
        mock_run.assert_called_once_with(
            ['sh', update_script_path(), 'develop'])

    def test_script_path_is_absolute(self):
        path = update_script_path()
        self.assertTrue(os.path.isabs(path))
        self.assertTrue(path.endswith('update_application.sh'))

    @patch('modules.update_handler.subprocess.run')
    def test_running_flag_is_set_while_script_runs(self, mock_run):
        import modules.update_handler as handler
        started = []

        def slow_run(*args, **kwargs):
            started.append(handler.is_update_running())

        mock_run.side_effect = slow_run
        trigger_update('main')
        # The guard is active while the script runs and released afterwards.
        self.assertEqual(started, [True])
        self.assertFalse(is_update_running())

    @patch('modules.update_handler.subprocess.run')
    def test_second_update_is_rejected_while_running(self, mock_run):
        import modules.update_handler as handler
        handler._update_running = True
        try:
            self.assertEqual(trigger_update('main'), "Update already running")
        finally:
            handler._update_running = False
        mock_run.assert_not_called()

    @patch('modules.update_handler.subprocess.run')
    def test_guard_is_released_on_failure(self, mock_run):
        mock_run.side_effect = OSError('script missing')
        with self.assertRaises(OSError):
            trigger_update('main')
        self.assertFalse(is_update_running())

    @patch('modules.update_handler.requests.get')
    def test_fetch_update_info_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "currentApplicationVersion": "v1.0.0",
            "whatChanged": "Test changes"
        }
        mock_get.return_value = mock_response

        result = fetch_update_info("main")

        self.assertIsNotNone(result)
        self.assertEqual(result["currentApplicationVersion"], "v1.0.0")
        self.assertEqual(result["whatChanged"], "Test changes")
        mock_get.assert_called_once_with(
            "https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend/refs/heads/main/info.json",
            timeout=10,
        )

    @patch('modules.update_handler.requests.get')
    def test_fetch_update_info_custom_branch(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"currentApplicationVersion": "v2.0.0"}
        mock_get.return_value = mock_response

        result = fetch_update_info("develop")

        self.assertIsNotNone(result)
        self.assertEqual(result["currentApplicationVersion"], "v2.0.0")
        mock_get.assert_called_once_with(
            "https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend/refs/heads/develop/info.json",
            timeout=10,
        )

    @patch('modules.update_handler.requests.get')
    def test_fetch_update_info_request_exception(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        result = fetch_update_info("main")

        self.assertIsNone(result)

    @patch('modules.update_handler.requests.get')
    def test_fetch_update_info_http_error(self, mock_get):
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        result = fetch_update_info("main")

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
