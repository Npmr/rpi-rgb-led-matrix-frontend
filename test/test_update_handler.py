import unittest
from unittest.mock import patch, MagicMock
import json

from modules.update_handler import trigger_update, fetch_update_info


class TestUpdateHandler(unittest.TestCase):

    @patch('modules.update_handler.subprocess.run')
    def test_trigger_update_default_branch(self, mock_run):
        result = trigger_update()
        self.assertEqual(result, "Update triggered successfully!")
        mock_run.assert_called_once_with(['sh', 'update_application.sh', 'main'])

    @patch('modules.update_handler.subprocess.run')
    def test_trigger_update_custom_branch(self, mock_run):
        result = trigger_update(branch="develop")
        self.assertEqual(result, "Update triggered successfully!")
        mock_run.assert_called_once_with(['sh', 'update_application.sh', 'develop'])

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
            "https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend/refs/heads/main/info.json"
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
            "https://raw.githubusercontent.com/Npmr/rpi-rgb-led-matrix-frontend/refs/heads/develop/info.json"
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
