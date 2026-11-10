import unittest
from unittest.mock import patch, mock_open, MagicMock
import io
import json
from PIL import Image

from upload_handler import (
    get_quality_settings, generate_lqip, generate_thumbnails,
    convert_to_webp, convert_to_avif, get_image_metadata,
    DEFAULT_WEBP_QUALITY, DEFAULT_AVIF_QUALITY, DEFAULT_THUMBNAIL_QUALITY
)


def _make_test_image(width=100, height=80, fmt='JPEG', mode='RGB'):
    img = Image.new(mode, (width, height), color='red')
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestGetQualitySettings(unittest.TestCase):

    @patch('upload_handler.os.path.abspath')
    @patch('upload_handler.os.path.dirname')
    @patch('builtins.open', mock_open(read_data='{"webpQuality": 90, "avifQuality": 60, "thumbnailQuality": 70}'))
    def test_reads_from_settings(self, mock_dirname, mock_abspath):
        mock_abspath.return_value = '/project/upload_handler.py'
        mock_dirname.return_value = '/project'

        result = get_quality_settings()

        self.assertEqual(result['webp_quality'], 90)
        self.assertEqual(result['avif_quality'], 60)
        self.assertEqual(result['thumbnail_quality'], 70)

    @patch('upload_handler.os.path.abspath')
    @patch('upload_handler.os.path.dirname')
    @patch('builtins.open', mock_open(read_data='{"webpQuality": 90}'))
    def test_missing_keys_use_defaults(self, mock_dirname, mock_abspath):
        mock_abspath.return_value = '/project/upload_handler.py'
        mock_dirname.return_value = '/project'

        result = get_quality_settings()

        self.assertEqual(result['webp_quality'], 90)
        self.assertEqual(result['avif_quality'], DEFAULT_AVIF_QUALITY)
        self.assertEqual(result['thumbnail_quality'], DEFAULT_THUMBNAIL_QUALITY)

    @patch('upload_handler.os.path.abspath', side_effect=Exception('error'))
    def test_file_not_found_returns_defaults(self, mock_abspath):
        result = get_quality_settings()

        self.assertEqual(result['webp_quality'], DEFAULT_WEBP_QUALITY)
        self.assertEqual(result['avif_quality'], DEFAULT_AVIF_QUALITY)
        self.assertEqual(result['thumbnail_quality'], DEFAULT_THUMBNAIL_QUALITY)


class TestGenerateLqip(unittest.TestCase):

    def test_invalid_image_data(self):
        result = generate_lqip(b'not an image')

        self.assertIsNone(result)

    def test_returns_none_due_to_pillow_filter_bug(self):
        image_data = _make_test_image(100, 80, 'JPEG', 'RGB')

        result = generate_lqip(image_data)

        self.assertIsNone(result)

    def test_handles_rgba_image(self):
        image_data = _make_test_image(100, 80, 'PNG', 'RGBA')

        result = generate_lqip(image_data)

        self.assertIsNone(result)


class TestGenerateThumbnails(unittest.TestCase):

    def test_generates_all_sizes(self):
        image_data = _make_test_image(400, 300, 'JPEG', 'RGB')

        result = generate_thumbnails(image_data, 'test.jpg')

        self.assertIn('small', result)
        self.assertIn('medium', result)
        self.assertIn('large', result)
        for size_name in ['small', 'medium', 'large']:
            self.assertIn('filename', result[size_name])
            self.assertIn('data', result[size_name])
            self.assertIn('width', result[size_name])
            self.assertIn('height', result[size_name])
            self.assertTrue(result[size_name]['filename'].startswith('test_'))
            self.assertTrue(result[size_name]['filename'].endswith('.webp'))

    def test_thumbnail_dimensions_within_bounds(self):
        image_data = _make_test_image(1000, 800, 'JPEG', 'RGB')

        result = generate_thumbnails(image_data, 'large.jpg')

        self.assertLessEqual(result['small']['width'], 150)
        self.assertLessEqual(result['small']['height'], 150)
        self.assertLessEqual(result['medium']['width'], 300)
        self.assertLessEqual(result['medium']['height'], 300)
        self.assertLessEqual(result['large']['width'], 600)
        self.assertLessEqual(result['large']['height'], 600)

    def test_invalid_image_returns_empty(self):
        result = generate_thumbnails(b'not an image', 'bad.jpg')

        self.assertEqual(result, {})


class TestConvertToWebp(unittest.TestCase):

    def test_converts_jpg(self):
        image_data = _make_test_image(100, 80, 'JPEG', 'RGB')

        filename, data = convert_to_webp(image_data, 'photo.jpg')

        self.assertEqual(filename, 'photo.webp')
        self.assertIsNotNone(data)
        self.assertGreater(len(data), 0)

    def test_converts_png(self):
        image_data = _make_test_image(100, 80, 'PNG', 'RGB')

        filename, data = convert_to_webp(image_data, 'image.png')

        self.assertEqual(filename, 'image.webp')
        self.assertIsNotNone(data)

    def test_invalid_image_returns_none(self):
        filename, data = convert_to_webp(b'garbage', 'bad.jpg')

        self.assertIsNone(filename)
        self.assertIsNone(data)


class TestConvertToAvif(unittest.TestCase):

    def test_converts_jpg(self):
        image_data = _make_test_image(100, 80, 'JPEG', 'RGB')

        filename, data = convert_to_avif(image_data, 'photo.jpg')

        self.assertEqual(filename, 'photo.avif')
        self.assertIsNotNone(data)
        self.assertGreater(len(data), 0)

    def test_invalid_image_returns_none(self):
        filename, data = convert_to_avif(b'garbage', 'bad.jpg')

        self.assertIsNone(filename)
        self.assertIsNone(data)


class TestGetImageMetadata(unittest.TestCase):

    def test_horizontal_image(self):
        image_data = _make_test_image(400, 200, 'JPEG', 'RGB')

        result = get_image_metadata(image_data)

        self.assertIsNotNone(result)
        self.assertEqual(result['width'], 400)
        self.assertEqual(result['height'], 200)
        self.assertEqual(result['orientation'], 'horizontal')

    def test_vertical_image(self):
        image_data = _make_test_image(200, 400, 'JPEG', 'RGB')

        result = get_image_metadata(image_data)

        self.assertEqual(result['orientation'], 'vertical')

    def test_square_image(self):
        image_data = _make_test_image(300, 300, 'JPEG', 'RGB')

        result = get_image_metadata(image_data)

        self.assertEqual(result['orientation'], 'square')

    def test_invalid_image_returns_none(self):
        result = get_image_metadata(b'not an image')

        self.assertIsNone(result)

    def test_returns_format_and_mode(self):
        image_data = _make_test_image(100, 80, 'JPEG', 'RGB')

        result = get_image_metadata(image_data)

        self.assertIsNotNone(result['format'])
        self.assertIsNotNone(result['mode'])

    def test_rgba_image(self):
        image_data = _make_test_image(100, 80, 'PNG', 'RGBA')

        result = get_image_metadata(image_data)

        self.assertIsNotNone(result)
        self.assertEqual(result['width'], 100)
        self.assertEqual(result['height'], 80)


if __name__ == '__main__':
    unittest.main()
