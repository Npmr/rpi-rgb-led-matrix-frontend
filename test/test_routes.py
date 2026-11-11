import unittest
from unittest.mock import patch, MagicMock
from app import app


class TestIndexRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.countMediaTypeAndNumber')
    def test_index_returns_200(self, mock_count):
        mock_count.return_value = ([], [], [])
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    @patch('app.countMediaTypeAndNumber')
    def test_index_contains_tabs(self, mock_count):
        mock_count.return_value = ([], [], [])
        response = self.client.get('/')
        data = response.data.decode()
        self.assertIn('Images', data)
        self.assertIn('GIFs', data)
        self.assertIn('Videos', data)
        self.assertIn('Demos', data)

    @patch('app.countMediaTypeAndNumber')
    def test_index_with_images(self, mock_count):
        images = [{'filename': 'test.jpg', 'orientation': 'horizontal', 'thumbnails': {}, 'webp_url': None, 'avif_url': None, 'lqip': None}]
        mock_count.return_value = (images, [], [])
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'test.jpg', response.data)

    @patch('app.countMediaTypeAndNumber')
    def test_index_with_gifs(self, mock_count):
        gifs = [{'filename': 'anim.gif', 'orientation': 'square', 'thumbnails': {}, 'lqip': None}]
        mock_count.return_value = ([], gifs, [])
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'anim.gif', response.data)

    @patch('app.countMediaTypeAndNumber')
    def test_index_with_videos(self, mock_count):
        videos = [{'filename': 'clip.webm', 'orientation': 'horizontal'}]
        mock_count.return_value = ([], [], videos)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'clip.webm', response.data)


class TestUploadRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.read_settings')
    @patch('app.getFreeDiskSpace')
    def test_upload_returns_200(self, mock_disk, mock_settings):
        mock_disk.return_value = (45.0, 55)
        mock_settings.return_value = {'widthInPixel': 64, 'heightInPixel': 32}
        response = self.client.get('/upload')
        self.assertEqual(response.status_code, 200)

    @patch('app.read_settings')
    @patch('app.getFreeDiskSpace')
    def test_upload_contains_form(self, mock_disk, mock_settings):
        mock_disk.return_value = (45.0, 55)
        mock_settings.return_value = {'widthInPixel': 64, 'heightInPixel': 32}
        response = self.client.get('/upload')
        data = response.data.decode()
        self.assertIn('upload_image', data)
        self.assertIn('dropzone', data)


class TestChangelogRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.fetch_update_info')
    @patch('app.read_settings')
    @patch('app.read_infos')
    def test_changelog_returns_200(self, mock_infos, mock_settings, mock_update):
        mock_infos.return_value = {
            'currentApplicationVersion': 'v1.0.0',
            'whatChanged': 'test',
            'changelog': []
        }
        mock_settings.return_value = {'updateBranch': 'main'}
        mock_update.return_value = {'currentApplicationVersion': 'v1.0.0', 'whatChanged': ''}
        response = self.client.get('/changelog')
        self.assertEqual(response.status_code, 200)

    @patch('app.fetch_update_info')
    @patch('app.read_settings')
    @patch('app.read_infos')
    def test_changelog_contains_version(self, mock_infos, mock_settings, mock_update):
        mock_infos.return_value = {
            'currentApplicationVersion': 'v1.0.0',
            'whatChanged': 'test',
            'changelog': [
                {'version': 'v1.0.0', 'date': '2026-01-01', 'changes': ['Feature A', 'Bug fix B']}
            ]
        }
        mock_settings.return_value = {'updateBranch': 'main'}
        mock_update.return_value = {'currentApplicationVersion': 'v1.0.0', 'whatChanged': ''}
        response = self.client.get('/changelog')
        data = response.data.decode()
        self.assertIn('v1.0.0', data)
        self.assertIn('Feature A', data)
        self.assertIn('Bug fix B', data)

    @patch('app.fetch_update_info')
    @patch('app.read_settings')
    @patch('app.read_infos')
    def test_changelog_empty(self, mock_infos, mock_settings, mock_update):
        mock_infos.return_value = {
            'currentApplicationVersion': 'v1.0.0',
            'whatChanged': '',
            'changelog': []
        }
        mock_settings.return_value = {'updateBranch': 'main'}
        mock_update.return_value = None
        response = self.client.get('/changelog')
        self.assertEqual(response.status_code, 200)


class TestSaveSettingsRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.save_settings')
    @patch('app.read_settings')
    @patch('app.validate_strftime', return_value=(True, ''))
    def test_save_settings_redirects(self, mock_validate, mock_read, mock_save):
        mock_read.return_value = {'updateBranch': 'main'}
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
        mock_save.assert_called_once()

    @patch('app.read_settings')
    @patch('app.validate_strftime', return_value=(False, 'Invalid format code: %Q'))
    def test_save_settings_invalid_strftime(self, mock_validate, mock_read):
        mock_read.return_value = {'updateBranch': 'main'}
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
            'clockFormatDate': '%Q', 'clockFormatTime': '%H:%M:%S'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Invalid format code', response.data)


class TestProcessDemoRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.Thread')
    @patch('app.process_image_async')
    def test_process_demo_redirects(self, mock_process, mock_thread):
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        response = self.client.post('/process_demo', data={'csrf_token': 'test', 'options': '0'})
        self.assertEqual(response.status_code, 302)
        mock_thread.assert_called_once()


class TestStopProcessRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.immich_controller')
    @patch('app.stopProcess')
    def test_stop_process_redirects(self, mock_stop, mock_immich):
        response = self.client.post('/stop_process', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)
        mock_stop.assert_called_once()
        mock_immich.stop_immich_loop.assert_called_once()


class TestDeleteImageRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.os.path.exists', return_value=False)
    @patch('app.os.remove')
    def test_delete_nonexistent_image_redirects(self, mock_remove, mock_exists):
        response = self.client.post('/delete_image', data={'csrf_token': 'test', 'image_name_to_delete': 'nonexistent.jpg'})
        self.assertEqual(response.status_code, 302)


class TestGiphyRoutes(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.giphy_controller')
    def test_start_giphy_web_redirects(self, mock_giphy):
        response = self.client.post('/start_giphy_web', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)
        mock_giphy.start_giphy_loop.assert_called_once()

    @patch('app.giphy_controller')
    def test_start_giphy_category_redirects(self, mock_giphy):
        response = self.client.post('/start_giphy_category', data={'csrf_token': 'test', 'giphy_category': 'art'})
        self.assertEqual(response.status_code, 302)
        mock_giphy.start_giphy_loop.assert_called_once_with(search_term='art')

    @patch('app.giphy_controller')
    def test_start_giphy_category_no_category(self, mock_giphy):
        response = self.client.post('/start_giphy_category', data={'csrf_token': 'test', 'giphy_category': ''})
        self.assertEqual(response.status_code, 400)

    @patch('app.giphy_controller')
    def test_get_art_design_subcategories(self, mock_giphy):
        mock_giphy.get_art_design_subcategories.return_value = [{'name': 'Art', 'name_encoded': 'art'}]
        response = self.client.get('/get_art_design_subcategories')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)


class TestImmichRoutes(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.immich_controller')
    def test_start_immich_random_redirects(self, mock_immich):
        response = self.client.post('/start_immich_random', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)
        mock_immich.start_immich_loop.assert_called_once_with("random")

    @patch('app.immich_controller')
    def test_start_immich_album_redirects(self, mock_immich):
        response = self.client.post('/start_immich_album', data={'csrf_token': 'test', 'immich_album_id': 'album123'})
        self.assertEqual(response.status_code, 302)
        mock_immich.start_immich_loop.assert_called_once_with("album", album_id="album123")

    @patch('app.immich_controller')
    def test_start_immich_album_no_id(self, mock_immich):
        response = self.client.post('/start_immich_album', data={'csrf_token': 'test', 'immich_album_id': ''})
        self.assertEqual(response.status_code, 400)

    @patch('app.immich_controller')
    def test_start_immich_search_redirects(self, mock_immich):
        response = self.client.post('/start_immich_search', data={'csrf_token': 'test', 'immich_search_query': 'vacation'})
        self.assertEqual(response.status_code, 302)
        mock_immich.start_immich_loop.assert_called_once_with("search", search_query="vacation")

    @patch('app.immich_controller')
    def test_start_immich_search_no_query(self, mock_immich):
        response = self.client.post('/start_immich_search', data={'csrf_token': 'test', 'immich_search_query': ''})
        self.assertEqual(response.status_code, 400)

    @patch('app.immich_controller')
    def test_stop_immich_redirects(self, mock_immich):
        response = self.client.post('/stop_immich', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)
        mock_immich.stop_immich_loop.assert_called_once()

    @patch('app.immich_handler')
    def test_get_immich_albums(self, mock_handler):
        mock_handler.get_albums.return_value = [{'id': 'a1', 'name': 'Album 1', 'assetCount': 10}]
        response = self.client.get('/get_immich_albums')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)


class TestRebootShutdownRoutes(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.reboot_system')
    def test_reboot_returns_result(self, mock_reboot):
        mock_reboot.return_value = "Reboot System now!"
        response = self.client.post('/reboot', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Reboot System now!', response.data)

    @patch('app.shutdown_system')
    def test_shutdown_returns_result(self, mock_shutdown):
        mock_shutdown.return_value = "Shutting down! Bye bye"
        response = self.client.post('/shutdown', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Shutting down! Bye bye', response.data)


class TestSyncTimeRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.sync_time')
    def test_sync_time_returns_result(self, mock_sync):
        mock_sync.return_value = "Time synchronization triggered"
        response = self.client.post('/sync_time', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Time synchronization triggered', response.data)


class TestRotateRoutes(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.Thread')
    @patch('app.trigger_rotation')
    def test_rotate_left_redirects(self, mock_rotation, mock_thread):
        mock_thread.return_value = MagicMock()
        response = self.client.post('/rotate_left', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)

    @patch('app.Thread')
    @patch('app.trigger_rotation')
    def test_rotate_right_redirects(self, mock_rotation, mock_thread):
        mock_thread.return_value = MagicMock()
        response = self.client.post('/rotate_right', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)


class TestLayoutRoutes(unittest.TestCase):

    GEOMETRY = {
        'width': 192,
        'height': 128,
        'rawWidth': 384,
        'rawHeight': 64,
        'cellW': 32,
        'cellH': 32,
        'cols': 6,
        'rows': 4,
        'rotation': 180,
        'pixelMapper': 'U-mapper;Rotate:180',
    }

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    @patch('app.is_grid_running', return_value=False)
    @patch('app.read_layout')
    @patch('app.get_display_geometry', return_value=GEOMETRY)
    @patch('app.read_settings', return_value={'widthInPixel': '32', 'heightInPixel': '32', 'chainLength': '12', 'parallelChains': '2'})
    def test_layout_returns_200(self, mock_settings, mock_geometry, mock_layout, mock_running):
        from modules.layout_handler import default_layout
        mock_layout.return_value = default_layout()
        response = self.client.get('/layout')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'matrix-board', response.data)
        # Grid geometry is derived from settings, not stored in the layout.
        html = response.get_data(as_text=True)
        self.assertIn('6 × 4', html)

    @patch('app.save_layout', return_value=True)
    @patch('app.get_display_geometry', return_value=GEOMETRY)
    @patch('app.read_settings', return_value={'widthInPixel': '32', 'heightInPixel': '32', 'chainLength': '12', 'parallelChains': '2'})
    def test_save_layout_valid(self, mock_settings, mock_geometry, mock_save):
        payload = {
            'enabled': False,
            'grid': {},
            'widgets': [
                {'id': 'a', 'type': 'clock', 'col': 0, 'row': 0, 'w': 2, 'h': 1}
            ],
        }
        response = self.client.post('/save_layout', json=payload, headers={'X-CSRF-Token': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['ok'])
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        self.assertNotIn('cellW', saved['grid'])
        self.assertNotIn('cellH', saved['grid'])

    @patch('app.save_layout', return_value=True)
    @patch('app.get_display_geometry', return_value=GEOMETRY)
    @patch('app.read_settings', return_value={'widthInPixel': '32', 'heightInPixel': '32', 'chainLength': '12', 'parallelChains': '2'})
    def test_save_layout_accepts_legacy_cell_keys(self, mock_settings, mock_geometry, mock_save):
        payload = {
            'enabled': False,
            'grid': {'cellW': 16, 'cellH': 16},
            'widgets': [
                {'id': 'a', 'type': 'clock', 'col': 0, 'row': 0, 'w': 2, 'h': 1}
            ],
        }
        response = self.client.post('/save_layout', json=payload, headers={'X-CSRF-Token': 'test'})
        self.assertEqual(response.status_code, 200)
        saved = mock_save.call_args[0][0]
        self.assertNotIn('cellW', saved['grid'])
        self.assertNotIn('cellH', saved['grid'])

    @patch('app.save_layout', return_value=True)
    @patch('app.get_display_geometry', return_value=GEOMETRY)
    @patch('app.read_settings', return_value={'widthInPixel': '32', 'heightInPixel': '32', 'chainLength': '12', 'parallelChains': '2'})
    def test_save_layout_overlap_rejected(self, mock_settings, mock_geometry, mock_save):
        payload = {
            'enabled': False,
            'grid': {},
            'widgets': [
                {'id': 'a', 'type': 'clock', 'col': 0, 'row': 0, 'w': 2, 'h': 1},
                {'id': 'b', 'type': 'static_text', 'col': 1, 'row': 0, 'w': 2, 'h': 1},
            ],
        }
        response = self.client.post('/save_layout', json=payload, headers={'X-CSRF-Token': 'test'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()['ok'])
        mock_save.assert_not_called()

    @patch('app.start_grid_display', return_value=True)
    def test_start_grid_redirects(self, mock_start):
        response = self.client.post('/start_grid', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)
        mock_start.assert_called_once()

    @patch('app.stop_grid_display')
    def test_stop_grid_redirects(self, mock_stop):
        response = self.client.post('/stop_grid', data={'csrf_token': 'test'})
        self.assertEqual(response.status_code, 302)
        mock_stop.assert_called_once()


class TestUpdateProcessRoute(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test'

    def _post(self, data=None):
        payload = {'csrf_token': 'test'}
        payload.update(data or {})
        return self.client.post('/update_process', data=payload)

    @patch('app.Thread')
    @patch('app.trigger_update')
    @patch('app.save_settings', return_value=True)
    @patch('app.read_settings', return_value={'updateBranch': 'main'})
    @patch('app.is_update_running', return_value=False)
    def test_starts_update_in_background(self, mock_running, mock_settings,
                                         mock_save, mock_trigger, mock_thread):
        response = self._post({'updateBranch': 'dev'})
        self.assertEqual(response.status_code, 302)
        mock_thread.assert_called_once_with(target=mock_trigger, args=('dev',),
                                            daemon=True)
        mock_thread.return_value.start.assert_called_once()

    @patch('app.Thread')
    @patch('app.trigger_update')
    @patch('app.save_settings', return_value=True)
    @patch('app.read_settings', return_value={'updateBranch': 'main'})
    @patch('app.is_update_running', return_value=False)
    def test_selected_branch_is_saved(self, mock_running, mock_settings,
                                      mock_save, mock_trigger, mock_thread):
        self._post({'updateBranch': 'dev'})
        saved = mock_save.call_args[0][0]
        self.assertEqual(saved['updateBranch'], 'dev')

    @patch('app.Thread')
    @patch('app.trigger_update')
    @patch('app.save_settings', return_value=True)
    @patch('app.read_settings', return_value={'updateBranch': 'main'})
    @patch('app.is_update_running', return_value=False)
    def test_unknown_branch_falls_back_to_main(self, mock_running,
                                               mock_settings, mock_save,
                                               mock_trigger, mock_thread):
        self._post({'updateBranch': '../../etc/passwd'})
        mock_thread.assert_called_once_with(target=mock_trigger, args=('main',),
                                            daemon=True)

    @patch('app.Thread')
    @patch('app.trigger_update')
    @patch('app.read_settings', return_value={'updateBranch': 'main'})
    @patch('app.is_update_running', return_value=True)
    def test_second_update_is_not_started(self, mock_running, mock_settings,
                                          mock_trigger, mock_thread):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        mock_thread.assert_not_called()
        with self.client.session_transaction() as sess:
            flashes = sess.get('_flashes', [])
        self.assertTrue(any(category == 'warning' for category, _ in flashes))

    @patch('app.trigger_update')
    def test_csrf_token_is_required(self, mock_trigger):
        response = self.client.post('/update_process', data={'updateBranch': 'main'})
        self.assertEqual(response.status_code, 403)
        mock_trigger.assert_not_called()

    @patch('app.fetch_update_info')
    @patch('app.read_settings')
    @patch('app.read_infos')
    def test_changelog_update_form_carries_csrf_token(self, mock_infos,
                                                      mock_settings,
                                                      mock_update):
        mock_infos.return_value = {
            'currentApplicationVersion': 'v1.0.0',
            'whatChanged': '',
            'changelog': [],
        }
        mock_settings.return_value = {'updateBranch': 'main'}
        mock_update.return_value = {'currentApplicationVersion': 'v2.0.0',
                                    'whatChanged': 'new'}
        response = self.client.get('/changelog')
        data = response.data.decode()
        self.assertIn('action="/update_process"', data)
        self.assertIn('name="csrf_token"', data)
        self.assertIn('Install Update', data)
        self.assertIn('v2.0.0 is available', data)

    @patch('app.is_update_running', return_value=True)
    @patch('app.fetch_update_info')
    @patch('app.read_settings')
    @patch('app.read_infos')
    def test_install_button_disabled_while_update_runs(self, mock_infos,
                                                       mock_settings,
                                                       mock_update,
                                                       mock_running):
        mock_infos.return_value = {
            'currentApplicationVersion': 'v1.0.0',
            'whatChanged': '',
            'changelog': [],
        }
        mock_settings.return_value = {'updateBranch': 'main'}
        mock_update.return_value = {'currentApplicationVersion': 'v2.0.0',
                                    'whatChanged': 'new'}
        data = self.client.get('/changelog').get_data(as_text=True)
        self.assertIn('An update is currently running', data)
        self.assertIn('disabled', data)


if __name__ == '__main__':
    unittest.main()
