import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import io
from PIL import Image

from modules.media_handler import determine_orientation, get_thumbnails, get_lqip, countMediaTypeAndNumber


class TestDetermineOrientation(unittest.TestCase):

    def _create_image(self, width, height, fmt='JPEG'):
        img = Image.new('RGB', (width, height), color='red')
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        buf.seek(0)
        return buf

    @patch('modules.media_handler.Image.open')
    def test_horizontal_image(self, mock_open):
        mock_img = MagicMock()
        mock_img.size = (400, 200)
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_img

        result = determine_orientation('test.jpg')
        self.assertEqual(result, 'horizontal')

    @patch('modules.media_handler.Image.open')
    def test_vertical_image(self, mock_open):
        mock_img = MagicMock()
        mock_img.size = (200, 400)
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_img

        result = determine_orientation('test.jpg')
        self.assertEqual(result, 'vertical')

    @patch('modules.media_handler.Image.open')
    def test_square_image(self, mock_open):
        mock_img = MagicMock()
        mock_img.size = (300, 300)
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_img

        result = determine_orientation('test.jpg')
        self.assertEqual(result, 'square')

    def test_file_not_found(self):
        result = determine_orientation('/nonexistent/path.jpg')
        self.assertEqual(result, 'unknown')


class TestGetThumbnails(unittest.TestCase):

    @patch('modules.media_handler.os.path.exists')
    def test_get_thumbnails_all_sizes(self, mock_exists):
        mock_exists.return_value = True

        result = get_thumbnails('/fake/static', 'test_image')

        self.assertIn('small', result)
        self.assertIn('medium', result)
        self.assertIn('large', result)
        self.assertEqual(result['small']['url'], '/static/pictures/thumbnails/test_image_thumb_small.webp')
        self.assertEqual(result['small']['width'], 150)
        self.assertEqual(result['small']['height'], 150)
        self.assertEqual(result['medium']['width'], 300)
        self.assertEqual(result['large']['width'], 600)

    @patch('modules.media_handler.os.path.exists')
    def test_get_thumbnails_none_exist(self, mock_exists):
        mock_exists.return_value = False

        result = get_thumbnails('/fake/static', 'test_image')

        self.assertEqual(result, {})

    @patch('modules.media_handler.os.path.exists')
    def test_get_thumbnails_partial(self, mock_exists):
        def side_effect(path):
            return 'medium' in path
        mock_exists.side_effect = side_effect

        result = get_thumbnails('/fake/static', 'test_image')

        self.assertNotIn('small', result)
        self.assertIn('medium', result)
        self.assertNotIn('large', result)


class TestGetLqip(unittest.TestCase):

    @patch('modules.media_handler.os.path.exists')
    def test_get_lqip_found(self, mock_exists):
        mock_exists.return_value = True

        with patch('builtins.open', mock_open(read_data='base64encodeddata')):
            result = get_lqip('/fake/static', 'test_image')

        self.assertEqual(result, 'base64encodeddata')

    @patch('modules.media_handler.os.path.exists')
    def test_get_lqip_not_found(self, mock_exists):
        mock_exists.return_value = False

        result = get_lqip('/fake/static', 'test_image')

        self.assertIsNone(result)

    @patch('modules.media_handler.os.path.exists')
    def test_get_lqip_strips_whitespace(self, mock_exists):
        mock_exists.return_value = True

        with patch('builtins.open', mock_open(read_data='  base64data  \n')):
            result = get_lqip('/fake/static', 'test_image')

        self.assertEqual(result, 'base64data')


class TestCountMediaTypeAndNumber(unittest.TestCase):

    @patch('modules.media_handler.get_lqip')
    @patch('modules.media_handler.get_thumbnails')
    @patch('modules.media_handler.determine_orientation')
    @patch('modules.media_handler.os.path.isdir')
    @patch('modules.media_handler.os.path.exists')
    @patch('modules.media_handler.os.listdir')
    def test_counts_images_gifs_videos(self, mock_listdir, mock_exists, mock_isdir, mock_orientation, mock_thumbnails, mock_lqip):
        mock_listdir.return_value = ['photo.jpg', 'animation.gif', 'clip.webm', 'picture.png']
        mock_exists.return_value = False
        mock_isdir.return_value = True
        mock_orientation.return_value = 'horizontal'
        mock_thumbnails.return_value = {}
        mock_lqip.return_value = None

        images, gifs, videos = countMediaTypeAndNumber('/fake/static')

        self.assertEqual(len(images), 2)
        self.assertEqual(len(gifs), 1)
        self.assertEqual(len(videos), 1)
        self.assertEqual(images[0]['filename'], 'photo.jpg')
        self.assertEqual(gifs[0]['filename'], 'animation.gif')
        self.assertEqual(videos[0]['filename'], 'clip.webm')

    @patch('modules.media_handler.get_lqip')
    @patch('modules.media_handler.get_thumbnails')
    @patch('modules.media_handler.determine_orientation')
    @patch('modules.media_handler.os.path.isdir')
    @patch('modules.media_handler.os.path.exists')
    @patch('modules.media_handler.os.listdir')
    def test_empty_directory(self, mock_listdir, mock_exists, mock_isdir, mock_orientation, mock_thumbnails, mock_lqip):
        mock_listdir.return_value = []
        mock_isdir.return_value = True

        images, gifs, videos = countMediaTypeAndNumber('/fake/static')

        self.assertEqual(images, [])
        self.assertEqual(gifs, [])
        self.assertEqual(videos, [])

    @patch('modules.media_handler.get_lqip')
    @patch('modules.media_handler.get_thumbnails')
    @patch('modules.media_handler.determine_orientation')
    @patch('modules.media_handler.os.path.isdir')
    @patch('modules.media_handler.os.path.exists')
    @patch('modules.media_handler.os.listdir')
    def test_ignores_non_media_files(self, mock_listdir, mock_exists, mock_isdir, mock_orientation, mock_thumbnails, mock_lqip):
        mock_listdir.return_value = ['readme.txt', 'data.csv', '.DS_Store']
        mock_exists.return_value = False
        mock_isdir.return_value = True

        images, gifs, videos = countMediaTypeAndNumber('/fake/static')

        self.assertEqual(images, [])
        self.assertEqual(gifs, [])
        self.assertEqual(videos, [])

    @patch('modules.media_handler.get_lqip')
    @patch('modules.media_handler.get_thumbnails')
    @patch('modules.media_handler.determine_orientation')
    @patch('modules.media_handler.os.path.isdir')
    @patch('modules.media_handler.os.path.exists')
    @patch('modules.media_handler.os.listdir')
    def test_jpeg_also_recognized(self, mock_listdir, mock_exists, mock_isdir, mock_orientation, mock_thumbnails, mock_lqip):
        mock_listdir.return_value = ['photo.jpeg']
        mock_exists.return_value = False
        mock_isdir.return_value = True
        mock_orientation.return_value = 'square'
        mock_thumbnails.return_value = {}
        mock_lqip.return_value = None

        images, gifs, videos = countMediaTypeAndNumber('/fake/static')

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['filename'], 'photo.jpeg')

    @patch('modules.media_handler.get_lqip')
    @patch('modules.media_handler.get_thumbnails')
    @patch('modules.media_handler.determine_orientation')
    @patch('modules.media_handler.os.path.isdir')
    @patch('modules.media_handler.os.path.exists')
    @patch('modules.media_handler.os.listdir')
    def test_webp_url_included_when_exists(self, mock_listdir, mock_exists, mock_isdir, mock_orientation, mock_thumbnails, mock_lqip):
        mock_listdir.return_value = ['photo.jpg']
        mock_orientation.return_value = 'horizontal'
        mock_thumbnails.return_value = {}
        mock_lqip.return_value = None
        mock_isdir.return_value = True

        def exists_side_effect(path):
            return path.endswith('.webp')
        mock_exists.side_effect = exists_side_effect

        images, gifs, videos = countMediaTypeAndNumber('/fake/static')

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['webp_url'], '/static/pictures/photo.webp')

    @patch('modules.media_handler.get_lqip')
    @patch('modules.media_handler.get_thumbnails')
    @patch('modules.media_handler.determine_orientation')
    @patch('modules.media_handler.os.path.isdir')
    @patch('modules.media_handler.os.path.exists')
    @patch('modules.media_handler.os.listdir')
    def test_video_gets_horizontal_orientation(self, mock_listdir, mock_exists, mock_isdir, mock_orientation, mock_thumbnails, mock_lqip):
        mock_listdir.return_value = ['clip.webm']
        mock_isdir.return_value = True

        images, gifs, videos = countMediaTypeAndNumber('/fake/static')

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]['orientation'], 'horizontal')


if __name__ == '__main__':
    unittest.main()
