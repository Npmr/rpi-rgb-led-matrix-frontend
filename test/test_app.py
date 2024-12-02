import json
import os
import unittest

from app import read_settings


class TestSettings(unittest.TestCase):
    def test_read_settings(self):
        # Create a temporary settings.json file for testing
        with open('test_settings.json', 'w') as f:
            json.dump({'heightInPixel': 480, 'widthInPixel': 640}, f)

        settings = read_settings('test_settings.json')
        self.assertEqual(settings['heightInPixel'], 480)
        self.assertEqual(settings['widthInPixel'], 640)

        # Remove the temporary file
        os.remove('test_settings.json')


if __name__ == '__main__':
    unittest.main()
