import re
import unittest
from html.parser import HTMLParser
from unittest.mock import patch, MagicMock
from app import app
from modules import startup_screen as startup


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

    def test_startup_text_size_and_scrolling_are_stored(self):
        saved = self._post(settings_form(startupScreenFontSize='13',
                                         startupScreenScroll='always',
                                         startupScreenScrollSpeed='24'))
        self.assertEqual(saved['startupScreenFontSize'], '13')
        self.assertEqual(saved['startupScreenScroll'], 'always')
        self.assertEqual(saved['startupScreenScrollSpeed'], '24')

    def test_invalid_startup_text_settings_fall_back(self):
        saved = self._post(settings_form(startupScreenFontSize='huge',
                                         startupScreenScroll='sideways',
                                         startupScreenScrollSpeed='999'))
        self.assertEqual(saved['startupScreenFontSize'], 'auto')
        self.assertEqual(saved['startupScreenScroll'], 'auto')
        self.assertEqual(saved['startupScreenScrollSpeed'],
                         str(startup.MAX_SCROLL_SPEED))

    def test_missing_startup_text_settings_keep_stored_values(self):
        saved = self._post(settings_form(startupScreenFontSize=None,
                                         startupScreenScroll=None,
                                         startupScreenScrollSpeed=None))
        self.assertEqual(saved['startupScreenFontSize'], 'auto')
        self.assertEqual(saved['startupScreenScroll'], 'auto')
        # BASE_SETTINGS has no speed, so the default is used.
        self.assertEqual(saved['startupScreenScrollSpeed'], '12')

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


class _FormStructureParser(HTMLParser):
    """Tracks <form> nesting and where buttons/inputs end up.

    It follows the HTML5 rule that makes the old markup fail: a <form> start
    tag that appears while a form is already open is ignored, and the first
    </form> then closes that open form. Parsing the rendered page this way
    reproduces the browser outcome without a browser.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.max_nesting = 0
        self.forms = []
        self.orphan_buttons = []
        self.orphan_inputs = []
        self._raw_depth = 0
        self._form_element = None
        self._button = None

    @property
    def buttons(self):
        found = [b for form in self.forms for b in form['buttons']]
        return found + self.orphan_buttons

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'form':
            # Raw nesting as written in the template, before normalisation.
            self._raw_depth += 1
            self.max_nesting = max(self.max_nesting, self._raw_depth)
            if self._form_element is not None:
                return  # ignored by the HTML parser, contents stay in the outer form
            form = {'action': attributes.get('action'), 'buttons': []}
            self.forms.append(form)
            self._form_element = form
        elif tag == 'button':
            button = {
                'type': (attributes.get('type') or 'submit').lower(),
                'formaction': attributes.get('formaction'),
                'text': '',
            }
            if self._form_element is not None:
                self._form_element['buttons'].append(button)
            else:
                self.orphan_buttons.append(button)
            self._button = button
        elif tag == 'input' and attributes.get('name'):
            if self._form_element is None:
                self.orphan_inputs.append(attributes['name'])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'form':
            self._raw_depth = max(0, self._raw_depth - 1)
            # The first </form> closes the (only) open form, even when it was
            # written to close a nested one.
            self._form_element = None
        elif tag == 'button':
            self._button = None

    def handle_data(self, data):
        if self._button is not None:
            self._button['text'] += data


class TestSettingsFormStructure(unittest.TestCase):
    """Regression tests for the nested-form bug fixed in v0.0.58.

    settings.html used to wrap the Shutdown/Reboot forms inside the
    /save_settings form. Chromium dropped the nested <form> tag and closed the
    settings form at the first </form>, so the Save button belonged to no form
    at all: clicking it sent no request, which looked like a broken save.
    """

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'
        with patch('app.read_infos', return_value={'currentApplicationVersion': 'v1'}), \
                patch('app.fetch_update_info', return_value=None), \
                patch('app.getFreeDiskSpace', return_value=(50.0, 10)), \
                patch('app.countMediaTypeAndNumber', return_value=([], [], [])), \
                patch('app.read_settings', return_value=dict(BASE_SETTINGS)), \
                patch('app.available_pictures', return_value=[]):
            response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)
        self.html = response.get_data(as_text=True)
        self.parser = _FormStructureParser()
        self.parser.feed(self.html)

    def test_forms_are_not_nested(self):
        self.assertEqual(
            self.parser.max_nesting, 1,
            'nested <form> elements are dropped by the browser parser and '
            'break the outer form')

    def test_save_button_belongs_to_the_settings_form(self):
        settings_forms = [f for f in self.parser.forms
                          if f['action'] == '/save_settings']
        self.assertEqual(len(settings_forms), 1)
        labels = [b['text'] for b in settings_forms[0]['buttons']]
        self.assertTrue(any('Save Settings' in label for label in labels))

    def test_no_submit_button_is_orphaned(self):
        orphans = [b for b in self.parser.orphan_buttons
                   if b['type'] in ('submit', '')]
        self.assertEqual([b['text'].strip() for b in orphans], [])

    def test_every_named_input_is_inside_a_form(self):
        self.assertEqual(self.parser.orphan_inputs, [])

    def test_maintenance_buttons_target_their_own_endpoints(self):
        targets = {b['formaction'] for b in self.parser.buttons}
        self.assertIn('/shutdown', targets)
        self.assertIn('/reboot', targets)

    def test_regenerate_buttons_post_to_the_regenerate_route(self):
        regenerate = [b for b in self.parser.buttons
                      if 'Regenerate Thumbnails' in b['text']]
        self.assertTrue(regenerate, 'no Regenerate Thumbnails button rendered')
        for button in regenerate:
            self.assertEqual(button['formaction'], '/regenerate_thumbnails')

    def test_nested_form_bug_would_be_detected(self):
        """The parser must actually catch the old markup."""
        broken = ('<form action="/save_settings"><input name="a">'
                  '<div><form action="/shutdown"><button>Shutdown</button>'
                  '</form></div><div><button id="save">Save Settings</button>'
                  '</div></form>')
        parser = _FormStructureParser()
        parser.feed(broken)
        self.assertEqual(parser.max_nesting, 2)
        self.assertTrue(any('Save Settings' in b['text']
                            for b in parser.orphan_buttons))


if __name__ == '__main__':
    unittest.main()
