import unittest
from unittest.mock import patch, MagicMock, mock_open
import requests
import sys
sys.path.insert(0, '/home/norman/develop/rpi-rgb-led-matrix-frontend')

import modules.immich_handler as immich_handler


class TestImmichHandler(unittest.TestCase):

    def setUp(self):
        self.mock_settings = {
            "immichApiKey": "test-api-key",
            "immichUrl": "http://immich.local:2283"
        }

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.post')
    def test_fetch_random_asset_success(self, mock_post, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "asset-1", "type": "IMAGE", "originalFileName": "test1.jpg"},
            {"id": "asset-2", "type": "IMAGE", "originalFileName": "test2.jpg"},
            {"id": "asset-3", "type": "VIDEO", "originalFileName": "test3.mp4"}
        ]
        mock_post.return_value = mock_response

        result = immich_handler.fetch_random_asset()
        
        self.assertIsNotNone(result)
        self.assertIn("asset-", result)
        self.assertTrue(result.endswith("/original"))
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json'], {"size": 50})
        self.assertIn("/api/search/random", call_args[0][0])

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.post')
    def test_fetch_random_asset_empty_response(self, mock_post, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_post.return_value = mock_response

        result = immich_handler.fetch_random_asset()
        self.assertIsNone(result)

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.post')
    def test_fetch_random_asset_404(self, mock_post, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_post.return_value = mock_response

        result = immich_handler.fetch_random_asset()
        self.assertIsNone(result)

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.get')
    def test_fetch_assets_by_album_success(self, mock_get, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "album-1",
            "albumName": "Test Album",
            "assets": [
                {"id": "asset-a", "type": "IMAGE"},
                {"id": "asset-b", "type": "IMAGE"}
            ]
        }
        mock_get.return_value = mock_response

        result = immich_handler.fetch_assets_by_album("album-1")
        
        self.assertIsNotNone(result)
        self.assertIn("asset-", result)
        self.assertTrue(result.endswith("/original"))
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn("/api/albums/album-1", call_args[0][0])

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.get')
    def test_fetch_assets_by_album_empty(self, mock_get, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "album-1", "albumName": "Empty", "assets": []}
        mock_get.return_value = mock_response

        result = immich_handler.fetch_assets_by_album("album-1")
        self.assertIsNone(result)

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.post')
    def test_search_assets_success(self, mock_post, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "assets": {
                "items": [
                    {"id": "search-1", "type": "IMAGE"},
                    {"id": "search-2", "type": "IMAGE"}
                ],
                "total": 2
            },
            "albums": {"items": [], "total": 0}
        }
        mock_post.return_value = mock_response

        results = immich_handler.search_assets("beach", 10)
        
        self.assertEqual(len(results), 2)
        for url in results:
            self.assertIn("search-", url)
            self.assertTrue(url.endswith("/original"))
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json'], {"query": "beach", "size": 10, "withExif": False})

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.post')
    def test_search_assets_no_results(self, mock_post, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"assets": {"items": [], "total": 0}}
        mock_post.return_value = mock_response

        results = immich_handler.search_assets("nonexistent")
        self.assertEqual(results, [])

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.get')
    def test_get_albums_success(self, mock_get, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "album-1", "albumName": "Vacation", "assetCount": 50},
            {"id": "album-2", "albumName": "Family", "assetCount": 30}
        ]
        mock_get.return_value = mock_response

        albums = immich_handler.get_albums()
        
        self.assertEqual(len(albums), 2)
        self.assertEqual(albums[0]["id"], "album-1")
        self.assertEqual(albums[0]["name"], "Vacation")
        self.assertEqual(albums[0]["assetCount"], 50)
        self.assertEqual(albums[1]["id"], "album-2")
        self.assertEqual(albums[1]["name"], "Family")

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.get')
    def test_download_asset_uses_original_fallback(self, mock_get, mock_read_settings):
        """Test that download_asset tries thumbnail first, falls back to original on 400/404"""
        mock_read_settings.return_value = self.mock_settings
        
        # First call: thumbnail returns 400 (fallback)
        mock_response_400 = MagicMock()
        mock_response_400.status_code = 400
        mock_response_400.close = MagicMock()
        
        # Second call: original succeeds
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.headers = {"Content-Type": "image/jpeg"}
        mock_response_ok.iter_content.return_value = [b"fake image data"]
        mock_response_ok.raise_for_status.return_value = None
        
        mock_get.side_effect = [mock_response_400, mock_response_ok]

        with patch('builtins.open', mock_open()) as mock_file:
            result = immich_handler.download_asset("asset-123")
            
            self.assertIsNotNone(result)
            self.assertTrue(result.endswith(".jpg"))
            self.assertEqual(mock_get.call_count, 2)
            
            # Verify first call was to thumbnail endpoint
            first_call = mock_get.call_args_list[0]
            self.assertIn("/thumbnail", first_call[0][0])
            self.assertEqual(first_call[1]['params'], {"size": "original", "edited": "true"})
            
            # Verify second call was to original endpoint
            second_call = mock_get.call_args_list[1]
            self.assertIn("/original", second_call[0][0])

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.get')
    def test_download_asset_direct_original_on_404(self, mock_get, mock_read_settings):
        """Test that download_asset falls back to original on 404 from thumbnail"""
        mock_read_settings.return_value = self.mock_settings
        
        # First call: thumbnail returns 404
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404
        mock_response_404.close = MagicMock()
        
        # Second call: original succeeds
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.headers = {"Content-Type": "image/png"}
        mock_response_ok.iter_content.return_value = [b"png data"]
        mock_response_ok.raise_for_status.return_value = None
        
        mock_get.side_effect = [mock_response_404, mock_response_ok]

        with patch('builtins.open', mock_open()) as mock_file:
            result = immich_handler.download_asset("asset-456")
            
            self.assertIsNotNone(result)
            self.assertTrue(result.endswith(".png"))
            self.assertEqual(mock_get.call_count, 2)

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.get')
    def test_download_asset_original_when_thumbnail_succeeds(self, mock_get, mock_read_settings):
        """Test that download_asset uses thumbnail response when it succeeds (200)"""
        mock_read_settings.return_value = self.mock_settings
        
        # First call: thumbnail succeeds
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.headers = {"Content-Type": "image/webp"}
        mock_response_ok.iter_content.return_value = [b"webp data"]
        mock_response_ok.raise_for_status.return_value = None
        
        mock_get.return_value = mock_response_ok

        with patch('builtins.open', mock_open()) as mock_file:
            result = immich_handler.download_asset("asset-789")
            
            self.assertIsNotNone(result)
            self.assertTrue(result.endswith(".webp"))
            self.assertEqual(mock_get.call_count, 1)
            # Should have called thumbnail endpoint only
            call_args = mock_get.call_args
            self.assertIn("/thumbnail", call_args[0][0])

    @patch('modules.immich_handler.read_settings')
    def test_missing_config_returns_none(self, mock_read_settings):
        mock_read_settings.return_value = {"immichApiKey": "", "immichUrl": ""}
        
        self.assertIsNone(immich_handler.fetch_random_asset())
        self.assertIsNone(immich_handler.fetch_assets_by_album("album-1"))
        self.assertEqual(immich_handler.search_assets("test"), [])
        self.assertEqual(immich_handler.get_albums(), [])
        self.assertIsNone(immich_handler.download_asset("asset-1"))

    @patch('modules.immich_handler.read_settings')
    @patch('modules.immich_handler.requests.post')
    def test_network_error_handling(self, mock_post, mock_read_settings):
        mock_read_settings.return_value = self.mock_settings
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        result = immich_handler.fetch_random_asset()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
