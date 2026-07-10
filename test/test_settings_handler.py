import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os

from modules.settings_handler import read_settings, save_settings


class TestSettingsHandler(unittest.TestCase):

    def test_read_settings_success(self):
        mock_data = {"heightInPixel": "32", "widthInPixel": "32"}
        mock_json = json.dumps(mock_data)

        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = read_settings("settings.json")

        self.assertEqual(result, mock_data)

    def test_read_settings_file_not_found(self):
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            result = read_settings("nonexistent.json")

        self.assertEqual(result, {})

    def test_read_settings_json_decode_error(self):
        invalid_json = "{ invalid json }"

        with patch('builtins.open', mock_open(read_data=invalid_json)):
            result = read_settings("invalid.json")

        self.assertEqual(result, {})

    @patch('modules.settings_handler.os.path.dirname')
    @patch('modules.settings_handler.os.path.abspath')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_settings_success(self, mock_open_file, mock_abspath, mock_dirname):
        # Mock the path construction
        mock_abspath.return_value = "/home/pi/rpi-rgb-led-matrix-frontend/modules/settings_handler.py"
        mock_dirname.side_effect = lambda x: "/home/pi/rpi-rgb-led-matrix-frontend/modules" if x == "/home/pi/rpi-rgb-led-matrix-frontend/modules/settings_handler.py" else "/home/pi/rpi-rgb-led-matrix-frontend"

        new_settings = {"heightInPixel": "64", "widthInPixel": "64"}

        result = save_settings(new_settings, "settings.json")

        self.assertTrue(result)
        # Verify file was opened for writing
        mock_open_file.assert_called_once()
        # Verify json.dump was called with correct data
        handle = mock_open_file()
        # Check that write was called with JSON data
        write_calls = handle.write.call_args_list
        self.assertTrue(len(write_calls) > 0)
        # The written data should contain our settings
        written_data = ''.join(call[0][0] for call in write_calls)
        self.assertIn("heightInPixel", written_data)
        self.assertIn("64", written_data)

    @patch('modules.settings_handler.os.path.dirname')
    @patch('modules.settings_handler.os.path.abspath')
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_save_settings_io_error(self, mock_open_file, mock_abspath, mock_dirname):
        mock_abspath.return_value = "/home/pi/rpi-rgb-led-matrix-frontend/modules/settings_handler.py"
        mock_dirname.side_effect = lambda x: "/home/pi/rpi-rgb-led-matrix-frontend/modules" if x == "/home/pi/rpi-rgb-led-matrix-frontend/modules/settings_handler.py" else "/home/pi/rpi-rgb-led-matrix-frontend"

        new_settings = {"heightInPixel": "64"}
        result = save_settings(new_settings, "settings.json")

        self.assertFalse(result)

    def test_save_settings_custom_filename(self):
        with patch('modules.settings_handler.os.path.dirname') as mock_dirname, \
             patch('modules.settings_handler.os.path.abspath') as mock_abspath, \
             patch('builtins.open', mock_open()) as mock_open_file:

            mock_abspath.return_value = "/home/pi/rpi-rgb-led-matrix-frontend/modules/settings_handler.py"
            mock_dirname.side_effect = lambda x: "/home/pi/rpi-rgb-led-matrix-frontend/modules" if x == "/home/pi/rpi-rgb-led-matrix-frontend/modules/settings_handler.py" else "/home/pi/rpi-rgb-led-matrix-frontend"

            new_settings = {"test": "value"}
            result = save_settings(new_settings, "custom_settings.json")

            self.assertTrue(result)
            mock_open_file.assert_called_once()


if __name__ == '__main__':
    unittest.main()
