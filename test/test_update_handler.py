import unittest
from unittest.mock import patch, MagicMock
import json
import os

from modules.update_handler import (
    trigger_update, fetch_update_info, update_script_path, is_update_running,
    fetch_branch_info, parse_version, compare_versions, normalize_branch,
    check_branch_update, branch_view, BRANCHES,
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

    @patch('modules.update_handler.requests.get')
    def test_fetch_branch_info_missing_branch(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        info, error = fetch_branch_info("dev")

        self.assertIsNone(info)
        self.assertEqual(error, "not-found")
        mock_response.raise_for_status.assert_not_called()

    @patch('modules.update_handler.requests.get')
    def test_fetch_branch_info_network_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("offline")

        info, error = fetch_branch_info("main")

        self.assertIsNone(info)
        self.assertEqual(error, "network")

    @patch('modules.update_handler.requests.get')
    def test_fetch_branch_info_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"currentApplicationVersion": "v1.0.0"}
        mock_get.return_value = mock_response

        info, error = fetch_branch_info("main")

        self.assertEqual(info["currentApplicationVersion"], "v1.0.0")
        self.assertIsNone(error)

    def test_parse_version(self):
        self.assertEqual(parse_version("v0.0.66"), (0, 0, 66))
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version(""), ())
        self.assertEqual(parse_version(None), ())

    def test_compare_versions(self):
        self.assertEqual(compare_versions("v0.0.66", "v0.0.66"), 0)
        self.assertEqual(compare_versions("v0.0.67", "v0.0.66"), 1)
        self.assertEqual(compare_versions("v0.0.65", "v0.0.66"), -1)
        self.assertEqual(compare_versions("v0.1", "v0.0.9"), 1)
        self.assertEqual(compare_versions("v1.0.0.1", "v1.0.0"), 1)
        # An unknown installed version still offers the remote update.
        self.assertEqual(compare_versions("v1.0.0", "unknown"), 1)
        self.assertEqual(compare_versions("unknown", "v1.0.0"), -1)
        self.assertEqual(compare_versions("unknown", "unknown"), 0)

    def test_normalize_branch(self):
        self.assertEqual(normalize_branch("dev"), "dev")
        self.assertEqual(normalize_branch("main"), "main")
        self.assertEqual(normalize_branch("../../etc/passwd"), "main")
        self.assertEqual(normalize_branch(None), "main")

    @patch('modules.update_handler.fetch_branch_info')
    def test_check_branch_update_available(self, mock_fetch):
        mock_fetch.return_value = (
            {"currentApplicationVersion": "v0.0.67", "whatChanged": "new"}, None)

        report = check_branch_update("dev", "v0.0.66")

        self.assertTrue(report["updateAvailable"])
        self.assertEqual(report["relation"], "available")
        self.assertEqual(report["version"], "v0.0.67")
        self.assertEqual(report["whatChanged"], "new")
        self.assertIsNone(report["error"])

    @patch('modules.update_handler.fetch_branch_info')
    def test_check_branch_update_up_to_date(self, mock_fetch):
        mock_fetch.return_value = (
            {"currentApplicationVersion": "v0.0.66"}, None)

        report = check_branch_update("main", "v0.0.66")

        self.assertFalse(report["updateAvailable"])
        self.assertEqual(report["relation"], "up-to-date")

    @patch('modules.update_handler.fetch_branch_info')
    def test_check_branch_update_local_newer(self, mock_fetch):
        mock_fetch.return_value = (
            {"currentApplicationVersion": "v0.0.60"}, None)

        report = check_branch_update("main", "v0.0.66")

        self.assertFalse(report["updateAvailable"])
        self.assertEqual(report["relation"], "local-newer")

    @patch('modules.update_handler.fetch_branch_info')
    def test_check_branch_update_missing_branch(self, mock_fetch):
        mock_fetch.return_value = (None, "not-found")

        report = check_branch_update("dev", "v0.0.66")

        self.assertFalse(report["updateAvailable"])
        self.assertEqual(report["error"], "not-found")
        self.assertIsNone(report["version"])

    @patch('modules.update_handler.fetch_branch_info')
    def test_check_branch_update_network_error(self, mock_fetch):
        mock_fetch.return_value = (None, "network")

        report = check_branch_update("main", "v0.0.66")

        self.assertFalse(report["updateAvailable"])
        self.assertEqual(report["error"], "network")

    def test_branch_view_unchecked(self):
        view = branch_view("dev", None, "v0.0.66")
        self.assertFalse(view["checked"])
        self.assertEqual(view["stateClass"], "unchecked")
        self.assertEqual(view["stateText"], "Not checked")

    def test_branch_view_available(self):
        report = {"branch": "dev", "version": "v0.0.67", "whatChanged": "",
                  "updateAvailable": True, "relation": "available",
                  "error": None}
        view = branch_view("dev", report, "v0.0.66")
        self.assertEqual(view["stateClass"], "available")
        self.assertIn("v0.0.67", view["note"])
        self.assertTrue(view["updateAvailable"])

    def test_branch_view_missing(self):
        report = {"branch": "dev", "version": None, "whatChanged": "",
                  "updateAvailable": False, "relation": "unknown",
                  "error": "not-found"}
        view = branch_view("dev", report, "v0.0.66")
        self.assertEqual(view["stateClass"], "missing")
        self.assertEqual(view["stateText"], "Branch not found")
        self.assertIn("does not exist on origin", view["note"])

    def test_branch_view_network_error(self):
        report = {"branch": "main", "version": None, "whatChanged": "",
                  "updateAvailable": False, "relation": "unknown",
                  "error": "network"}
        view = branch_view("main", report, "v0.0.66")
        self.assertEqual(view["stateClass"], "unknown")
        self.assertEqual(view["stateText"], "Check failed")

    def test_branch_view_local_newer(self):
        report = {"branch": "main", "version": "v0.0.60", "whatChanged": "",
                  "updateAvailable": False, "relation": "local-newer",
                  "error": None}
        view = branch_view("main", report, "v0.0.66")
        self.assertEqual(view["stateClass"], "local-newer")
        self.assertIn("older", view["note"])

    def test_branch_labels_cover_all_branches(self):
        from modules.update_handler import BRANCH_LABELS
        for branch in BRANCHES:
            self.assertIn(branch, BRANCH_LABELS)


if __name__ == '__main__':
    unittest.main()
