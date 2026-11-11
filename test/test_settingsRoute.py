import re
import unittest
from unittest.mock import patch, MagicMock
from app import app


BASE_SETTINGS = {
    'heightInPixel': '32', 'widthInPixel': '32',
    'direction': 'vertical', 'updateBranch': 'main',
    'language': 'en', 'displayTimeAndDate': 'checked',
    'mqttIP': '192.168.1.1', 'mqttPort': '1883',
    'deviceID': 'test', 'deviceName': 'Test',
    'giphyApiKey': '', 'displayBrightness': '80',
    'chainLength': '1', 'parallelChains': '1',
    'ledSlowdown': '2', 'playlistTime': '30',
    'timezone': 'UTC', 'clockFormatDate': '%A',
    'clockFormatTime': '%H:%M:%S',
    'imageFitMode': 'cover', 'imageFitAnchor': 'center',
    'startupScreenEnabled': '', 'startupScreenImage': '',
    'startupScreenText': 'Welcome', 'startupScreenDuration': '30',
}


def settings_form(**overrides):
    data = {
        'csrf_token': 'test',
        'height': '32', 'width': '32', 'direction': 'vertical',
        'chainLength': '1', 'parallelChains': '1', 'ledSlowdown': '2',
        'playlistTime': '30', 'displayBrightness': '80',
        'mqttIP': '192.168.1.1', 'mqttPort': '1883',
        'deviceID': 'test_device', 'deviceName': 'Test Display',
        'giphyApiKey': 'test_key', 'webpQuality': '85',
        'avifQuality': '50', 'thumbnailQuality': '80',
        'language': 'de', 'timezone': 'UTC',
        'clockFormatDate': '%A', 'clockFormatTime': '%H:%M:%S',
        'imageFitMode': 'cover', 'imageFitAnchor': 'center',
        'startupScreenText': 'Welcome', 'startupScreenDuration': '30',
    }
    for key in overrides:
        if overrides[key] is None:
            data.pop(key, None)
        else:
            data[key] = overrides[key]
    return data


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
        self.assertIn(b'name="direction"', response.data)
        self.assertIn(b'name="imageFitMode"', response.data)
        self.assertIn(b'name="imageFitAnchor"', response.data)
        self.assertIn(b'name="startupScreenEnabled"', response.data)
        self.assertIn(b'name="startupScreenImage"', response.data)
        self.assertIn(b'name="startupScreenText"', response.data)
        self.assertIn(b'name="startupScreenDuration"', response.data)

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


class TestSaveSettingsDisplayOptions(unittest.TestCase):
    """Orientation, image scaling and startup screen form handling."""

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    def _post(self, data, pictures=('a.png', 'b.gif'), grid_running=False):
        saved = {}

        def capture(settings):
            saved.update(settings)
            return True

        with patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.save_settings', side_effect=capture), \
                patch('app.available_pictures', return_value=list(pictures)), \
                patch('app.is_grid_running', return_value=grid_running), \
                patch('app.start_grid_display') as mock_grid, \
                patch('app.validate_strftime', return_value=(True, '')):
            response = self.client.post('/save_settings', data=data)
            mock_grid.assert_not_called()
        self.assertEqual(response.status_code, 302)
        return saved

    def test_save_without_direction_keeps_stored_value(self):
        saved = self._post(settings_form(direction=None))
        self.assertEqual(saved['direction'], 'vertical')

    def test_new_direction_is_stored(self):
        saved = self._post(settings_form(direction='horizontalTurned'))
        self.assertEqual(saved['direction'], 'horizontalTurned')

    def test_unknown_direction_falls_back_to_stored_value(self):
        saved = self._post(settings_form(direction='sideways'))
        self.assertEqual(saved['direction'], 'vertical')

    def test_image_fit_settings_are_stored(self):
        saved = self._post(settings_form(imageFitMode='contain',
                                         imageFitAnchor='top'))
        self.assertEqual(saved['imageFitMode'], 'contain')
        self.assertEqual(saved['imageFitAnchor'], 'top')

    def test_invalid_image_fit_settings_fall_back(self):
        saved = self._post(settings_form(imageFitMode='zoom',
                                         imageFitAnchor='middle'))
        self.assertEqual(saved['imageFitMode'], 'cover')
        self.assertEqual(saved['imageFitAnchor'], 'center')

    def test_startup_screen_settings_are_stored(self):
        saved = self._post(settings_form(startupScreenEnabled='on',
                                         startupScreenImage='b.gif',
                                         startupScreenText='Hello',
                                         startupScreenDuration='45'))
        self.assertEqual(saved['startupScreenEnabled'], 'on')
        self.assertEqual(saved['startupScreenImage'], 'b.gif')
        self.assertEqual(saved['startupScreenText'], 'Hello')
        self.assertEqual(saved['startupScreenDuration'], '45')

    def test_startup_image_must_come_from_the_library(self):
        saved = self._post(settings_form(startupScreenImage='../../etc/passwd'))
        self.assertEqual(saved['startupScreenImage'], '')

    def test_startup_screen_disabled_when_toggle_is_off(self):
        saved = self._post(settings_form(startupScreenEnabled=None))
        self.assertEqual(saved['startupScreenEnabled'], '')

    def test_brightness_and_duration_are_stored(self):
        saved = self._post(settings_form(displayBrightness='65',
                                         playlistTime='120'))
        self.assertEqual(saved['displayBrightness'], '65')
        self.assertEqual(saved['playlistTime'], '120')

    def test_missing_brightness_and_duration_keep_stored_values(self):
        # Regression: these two fields were removed from the page in v0.0.52
        # while the route still required them, so every save returned 400.
        saved = self._post(settings_form(displayBrightness=None,
                                         playlistTime=None))
        self.assertEqual(saved['displayBrightness'], '80')
        self.assertEqual(saved['playlistTime'], '30')

    def test_missing_language_and_branch_keep_stored_values(self):
        # Neither field is rendered on the settings page; saving must not
        # reset them to None/"main".
        saved = self._post(settings_form(language=None, updateBranch=None))
        self.assertEqual(saved['language'], 'en')
        self.assertEqual(saved['updateBranch'], 'main')

    def test_missing_language_keeps_custom_branch(self):
        settings = dict(BASE_SETTINGS, updateBranch='dev', language='de')
        saved = {}
        with patch('app.read_settings', return_value=settings), \
                patch('app.save_settings', side_effect=lambda s: saved.update(s) or True), \
                patch('app.available_pictures', return_value=[]), \
                patch('app.is_grid_running', return_value=False), \
                patch('app.validate_strftime', return_value=(True, '')):
            response = self.client.post('/save_settings',
                                        data=settings_form(language=None,
                                                           updateBranch=None))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(saved['updateBranch'], 'dev')
        self.assertEqual(saved['language'], 'de')

    def test_empty_numeric_fields_keep_stored_values(self):
        saved = self._post(settings_form(displayBrightness='',
                                         playlistTime='',
                                         height='', width=''))
        self.assertEqual(saved['displayBrightness'], '80')
        self.assertEqual(saved['playlistTime'], '30')
        self.assertEqual(saved['heightInPixel'], '32')
        self.assertEqual(saved['widthInPixel'], '32')

    def test_post_with_only_the_rendered_form_fields(self):
        """Contract test: whatever the page renders must be enough to save."""
        with patch('app.read_infos', return_value={'currentApplicationVersion': 'v1'}), \
                patch('app.fetch_update_info', return_value=None), \
                patch('app.getFreeDiskSpace', return_value=(50.0, 10)), \
                patch('app.countMediaTypeAndNumber', return_value=([], [], [])), \
                patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.available_pictures', return_value=[]):
            page = self.client.get('/settings')
        self.assertEqual(page.status_code, 200)
        names = sorted(set(re.findall(r'name="([^"]+)"',
                                      page.get_data(as_text=True))))
        self.assertIn('csrf_token', names)
        self.assertIn('displayBrightness', names)
        self.assertIn('playlistTime', names)

        data = {name: '1' for name in names}
        data['csrf_token'] = 'test'
        data['imageFitMode'] = 'cover'
        data['imageFitAnchor'] = 'center'
        data['direction'] = 'vertical'
        data['startupScreenImage'] = ''
        data['timezone'] = 'UTC'
        data['clockFormatDate'] = '%A'
        data['clockFormatTime'] = '%H:%M:%S'

        with patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.save_settings', return_value=True) as mock_save, \
                patch('app.available_pictures', return_value=[]), \
                patch('app.is_grid_running', return_value=False):
            response = self.client.post('/save_settings', data=data)
        self.assertEqual(response.status_code, 302)
        mock_save.assert_called_once()

    def test_failed_write_shows_an_error_flash(self):
        with patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.save_settings', return_value=False), \
                patch('app.available_pictures', return_value=[]), \
                patch('app.is_grid_running', return_value=False), \
                patch('app.validate_strftime', return_value=(True, '')):
            response = self.client.post('/save_settings', data=settings_form())
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            flashes = sess.get('_flashes', [])
        self.assertTrue(any(category == 'error' for category, _ in flashes))

    def test_successful_write_shows_a_success_flash(self):
        with patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.save_settings', return_value=True), \
                patch('app.available_pictures', return_value=[]), \
                patch('app.is_grid_running', return_value=False), \
                patch('app.validate_strftime', return_value=(True, '')):
            response = self.client.post('/save_settings', data=settings_form())
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            flashes = sess.get('_flashes', [])
        self.assertIn(('success', 'Settings saved.'), flashes)

    def test_grid_restarts_when_geometry_changes(self):
        with patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.save_settings', return_value=True), \
                patch('app.available_pictures', return_value=[]), \
                patch('app.is_grid_running', return_value=True), \
                patch('app.start_grid_display') as mock_grid, \
                patch('app.validate_strftime', return_value=(True, '')):
            response = self.client.post(
                '/save_settings',
                data=settings_form(direction='horizontalTurned'))
        self.assertEqual(response.status_code, 302)
        mock_grid.assert_called_once()

    def test_grid_keeps_running_when_geometry_is_unchanged(self):
        with patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.save_settings', return_value=True), \
                patch('app.available_pictures', return_value=[]), \
                patch('app.is_grid_running', return_value=True), \
                patch('app.start_grid_display') as mock_grid, \
                patch('app.validate_strftime', return_value=(True, '')):
            response = self.client.post(
                '/save_settings',
                data=settings_form(displayBrightness='60'))
        self.assertEqual(response.status_code, 302)
        mock_grid.assert_not_called()


if __name__ == '__main__':
    unittest.main()
