import unittest
from unittest.mock import patch, MagicMock
from app import app


class TestSettingsRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.read_infos')
    @patch('app.fetch_update_info')
    @patch('app.getFreeDiskSpace')
    @patch('app.countMediaTypeAndNumber')
    @patch('app.read_settings')
    def test_settings_route(self, mock_read_settings, mock_countMediaTypeAndNumber,
                            mock_getFreeDiskSpace, mock_fetch_update_info, mock_read_infos):
        mock_read_settings.return_value = {
            'heightInPixel': 480, 'widthInPixel': 640,
            'direction': 'vertical', 'updateBranch': 'main',
            'language': 'en', 'displayTimeAndDate': 'checked',
            'mqttIP': '192.168.1.1', 'mqttPort': '1883',
            'deviceID': 'test', 'deviceName': 'Test',
            'giphyApiKey': '', 'displayBrightness': '80',
            'chainLength': '1', 'parallelChains': '1',
            'ledSlowdown': '2', 'playlistTime': '30',
            'timezone': 'UTC', 'clockFormatDate': '%A',
            'clockFormatTime': '%H:%M:%S'
        }
        mock_countMediaTypeAndNumber.return_value = ([10], [5], [2])
        mock_getFreeDiskSpace.return_value = (45.0, 55)
        mock_fetch_update_info.return_value = {'currentApplicationVersion': 'v1.0.0', 'whatChanged': 'test'}
        mock_read_infos.return_value = {'currentApplicationVersion': 'v1.0.0', 'whatChanged': 'test'}

        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Save Settings', response.data)

    @patch('app.save_settings')
    @patch('app.read_settings')
    @patch('app.validate_strftime', return_value=(True, ''))
    def test_save_settings_route(self, mock_validate, mock_read_settings, mock_save_settings):
        mock_read_settings.return_value = {'updateBranch': 'main'}

        response = self.client.post('/save_settings', data={
            'csrf_token': 'test',
            'height': '32', 'width': '32', 'direction': 'vertical',
            'chainLength': '1', 'parallelChains': '1', 'ledSlowdown': '2',
            'playlistTime': '30', 'displayBrightness': '80',
            'mqttIP': '192.168.1.1', 'mqttPort': '1883',
            'deviceID': 'test_device', 'deviceName': 'Test Display',
            'giphyApiKey': 'test_key', 'webpQuality': '85',
            'avifQuality': '50', 'thumbnailQuality': '80',
            'language': 'de', 'timezone': 'UTC',
            'clockFormatDate': '%A', 'clockFormatTime': '%H:%M:%S'
        })

        self.assertEqual(response.status_code, 302)
        mock_save_settings.assert_called_once()


if __name__ == '__main__':
    unittest.main()
