import io
import unittest
from unittest.mock import patch

from PIL import Image

from app import app


class TestBotEventRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['_csrf_token'] = 'test-token'
        self.headers = {'X-CSRF-Token': 'test-token'}

    @patch('app.bot_bus.publish')
    def test_json_event_is_queued(self, publish):
        publish.return_value = {'type': 'meeting_soon', '_id': 'abc'}
        response = self.client.post(
            '/bot/event',
            json={'type': 'meeting_soon', 'text': 'Standup'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['reaction']['mood'], 'alarmed')
        self.assertEqual(data['reaction']['priority'], 7)
        publish.assert_called_once_with(
            {'type': 'meeting_soon', 'text': 'Standup'}, source='rest'
        )

    @patch('app.bot_bus.publish')
    def test_plain_text_becomes_a_message(self, publish):
        publish.return_value = {'type': 'message'}
        response = self.client.post(
            '/bot/event', data='Dinner is ready', content_type='text/plain',
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        publish.assert_called_once_with(
            {'type': 'message', 'text': 'Dinner is ready'}, source='rest'
        )

    def test_empty_body_is_rejected(self):
        response = self.client.post('/bot/event', data='', headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_non_object_json_is_rejected(self):
        response = self.client.post('/bot/event', json=[1, 2, 3], headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_event_without_content_is_rejected(self):
        response = self.client.post('/bot/event', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    @patch('app.bot_bus.publish', side_effect=OSError('disk full'))
    def test_queue_failure_returns_500(self, _publish):
        response = self.client.post(
            '/bot/event', json={'type': 'message', 'text': 'Hi'},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 500)


class TestBotStateRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    @patch('app.bot_bus.count', return_value=2)
    @patch('app.read_settings')
    def test_state_reports_sleep_and_queue(self, settings, _count):
        settings.return_value = {
            'botSleepEnabled': 'off',
            'botSleepStart': '22:00',
            'botSleepEnd': '07:00',
            'timezone': 'UTC',
        }
        response = self.client.get('/bot/state')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data['sleeping'])
        self.assertEqual(data['queuedEvents'], 2)
        self.assertIn('happy', data['moods'])


class TestBotPreviewRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_preview_returns_a_png(self):
        response = self.client.get('/bot/preview.png?style=robot&mood=happy&w=64&h=64')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        self.assertTrue(response.data.startswith(b'\x89PNG'))

    def test_every_style_renders(self):
        for style in ('robot', 'emoji', 'screen'):
            response = self.client.get(f'/bot/preview.png?style={style}&w=32&h=32')
            with self.subTest(style=style):
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data.startswith(b'\x89PNG'))

    def test_unknown_style_and_mood_fall_back(self):
        response = self.client.get('/bot/preview.png?style=nope&mood=nope')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'\x89PNG'))

    def test_size_is_clamped(self):
        response = self.client.get('/bot/preview.png?w=99999&h=notanumber')
        self.assertEqual(response.status_code, 200)
        image = Image.open(io.BytesIO(response.data))
        self.assertEqual(image.width, 512)
        self.assertEqual(image.height, 64)

    def test_custom_colour_is_accepted(self):
        response = self.client.get('/bot/preview.png?color=%23ff0000&accent=%2300ff00')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'\x89PNG'))


if __name__ == '__main__':
    unittest.main()
