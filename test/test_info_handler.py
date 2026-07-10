import unittest
from unittest.mock import patch, mock_open
import json

from modules.info_handler import read_infos


class TestInfoHandler(unittest.TestCase):

    def test_read_infos_success(self):
        mock_data = {
            "currentApplicationVersion": "v1.0.0",
            "changelog": []
        }
        mock_json = json.dumps(mock_data)

        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = read_infos("info.json")

        self.assertEqual(result, mock_data)

    def test_read_infos_file_not_found(self):
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            result = read_infos("nonexistent.json")

        self.assertEqual(result, {})

    def test_read_infos_json_decode_error(self):
        invalid_json = "{ invalid json }"

        with patch('builtins.open', mock_open(read_data=invalid_json)):
            result = read_infos("invalid.json")

        self.assertEqual(result, {})

    def test_read_infos_empty_file(self):
        with patch('builtins.open', mock_open(read_data="")):
            result = read_infos("empty.json")

        self.assertEqual(result, {})

    def test_read_infos_custom_filename(self):
        mock_data = {"version": "v2.0.0"}
        mock_json = json.dumps(mock_data)

        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = read_infos("custom_info.json")

        self.assertEqual(result, mock_data)


if __name__ == '__main__':
    unittest.main()
