import unittest
from unittest.mock import patch
from app import app

class TestSettingsRoute(unittest.TestCase):

    def setUp(self):

        self.app = app.test_client()

    @patch('app.read_settings', return_value={'heightInPixel': 480, 'widthInPixel': 640, 'direction': 'vertical', 'updateBranch': 'main'})
    @patch('app.countMediaTypeAndNumber')
    def test_settings_route(self, mock_countMediaTypeAndNumber, mock_read_settings):
        # Simulate the function returning predefined values
        mock_countMediaTypeAndNumber.return_value = ([10], [5])  # Example values

        response = self.app.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Save Settings', response.data)
        self.assertIn(b'Settings', response.data)

    @patch('app.read_settings', return_value={'heightInPixel': 480, 'widthInPixel': 640, 'direction': 'vertical', 'updateBranch': 'main'})
    @patch('app.countMediaTypeAndNumber')
    def test_save_settings_route(self, mock_countMediaTypeAndNumber, mock_read_settings):
        # Simulate the function returning predefined values
        mock_countMediaTypeAndNumber.return_value = ([10], [5])  # Example values

        response = self.app.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Save Settings', response.data)
        self.assertIn(b'Settings', response.data)

if __name__ == '__main__':
    unittest.main()