import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

from modules.display_control import (
    get_pixel_mapper_config, get_matrix_dimensions,
    apply_exif_orientation, fill_crop_image
)


class TestGetPixelMapperConfig(unittest.TestCase):

    def test_single_chain_no_umapper(self):
        settings = {'parallelChains': 1, 'chainLength': 1}
        result = get_pixel_mapper_config(settings, 90)
        self.assertEqual(result, 'Rotate:90')

    def test_parallel_gt1_chain_short_no_umapper(self):
        settings = {'parallelChains': 2, 'chainLength': 3}
        result = get_pixel_mapper_config(settings, 180)
        self.assertEqual(result, 'Rotate:180')

    def test_parallel_gt1_chain_odd_no_umapper(self):
        settings = {'parallelChains': 2, 'chainLength': 5}
        result = get_pixel_mapper_config(settings, 270)
        self.assertEqual(result, 'Rotate:270')

    def test_umapper_parallel2_chain4(self):
        settings = {'parallelChains': 2, 'chainLength': 4}
        result = get_pixel_mapper_config(settings, 90)
        self.assertEqual(result, 'U-mapper;Rotate:90')

    def test_umapper_parallel3_chain6(self):
        settings = {'parallelChains': 3, 'chainLength': 6}
        result = get_pixel_mapper_config(settings, 180)
        self.assertEqual(result, 'U-mapper;Rotate:180')

    def test_parallel1_chain4_no_umapper(self):
        settings = {'parallelChains': 1, 'chainLength': 4}
        result = get_pixel_mapper_config(settings, 0)
        self.assertEqual(result, 'Rotate:0')

    def test_defaults_when_missing(self):
        settings = {}
        result = get_pixel_mapper_config(settings, 45)
        self.assertEqual(result, 'Rotate:45')


class TestGetMatrixDimensions(unittest.TestCase):

    def test_single_module_single_chain(self):
        settings = {'widthInPixel': 32, 'heightInPixel': 32, 'chainLength': 1, 'parallelChains': 1}
        w, h = get_matrix_dimensions(settings)
        self.assertEqual(w, 32)
        self.assertEqual(h, 32)

    def test_multi_chain(self):
        settings = {'widthInPixel': 32, 'heightInPixel': 32, 'chainLength': 4, 'parallelChains': 1}
        w, h = get_matrix_dimensions(settings)
        self.assertEqual(w, 128)
        self.assertEqual(h, 32)

    def test_multi_parallel(self):
        settings = {'widthInPixel': 32, 'heightInPixel': 32, 'chainLength': 1, 'parallelChains': 2}
        w, h = get_matrix_dimensions(settings)
        self.assertEqual(w, 32)
        self.assertEqual(h, 64)

    def test_both_multi(self):
        settings = {'widthInPixel': 64, 'heightInPixel': 64, 'chainLength': 3, 'parallelChains': 2}
        w, h = get_matrix_dimensions(settings)
        self.assertEqual(w, 192)
        self.assertEqual(h, 128)


class TestApplyExifOrientation(unittest.TestCase):

    def _make_image(self, width=100, height=60):
        return Image.new('RGB', (width, height), color='blue')

    def test_orientation_1_no_change(self):
        img = self._make_image()
        result = apply_exif_orientation(img, 1)
        self.assertEqual(result.size, img.size)

    def test_none_orientation(self):
        img = self._make_image()
        result = apply_exif_orientation(img, None)
        self.assertEqual(result.size, img.size)

    def test_orientation_6_rotate_270(self):
        img = self._make_image(100, 60)
        result = apply_exif_orientation(img, 6)
        self.assertEqual(result.size, (60, 100))

    def test_orientation_8_rotate_90(self):
        img = self._make_image(100, 60)
        result = apply_exif_orientation(img, 8)
        self.assertEqual(result.size, (60, 100))

    def test_orientation_3_rotate_180(self):
        img = self._make_image()
        result = apply_exif_orientation(img, 3)
        self.assertEqual(result.size, img.size)

    def test_orientation_2_flip_horizontal(self):
        img = self._make_image()
        result = apply_exif_orientation(img, 2)
        self.assertEqual(result.size, img.size)

    def test_orientation_4_flip_vertical(self):
        img = self._make_image()
        result = apply_exif_orientation(img, 4)
        self.assertEqual(result.size, img.size)

    def test_invalid_string_orientation(self):
        img = self._make_image()
        result = apply_exif_orientation(img, 'invalid')
        self.assertEqual(result.size, img.size)

    def test_out_of_range_orientation(self):
        img = self._make_image()
        result = apply_exif_orientation(img, 99)
        self.assertEqual(result.size, img.size)


class TestFillCropImage(unittest.TestCase):

    def test_already_correct_ratio(self):
        img = Image.new('RGB', (200, 200), color='green')
        result = fill_crop_image(img, 100, 100)
        self.assertEqual(result.size, (100, 100))

    def test_wider_image_crops_sides(self):
        img = Image.new('RGB', (400, 100), color='red')
        result = fill_crop_image(img, 100, 100)
        self.assertEqual(result.size, (100, 100))

    def test_taller_image_crops_top_bottom(self):
        img = Image.new('RGB', (100, 400), color='blue')
        result = fill_crop_image(img, 100, 100)
        self.assertEqual(result.size, (100, 100))

    def test_16by9_wide_to_square(self):
        img = Image.new('RGB', (320, 180), color='yellow')
        result = fill_crop_image(img, 64, 64)
        self.assertEqual(result.size, (64, 64))

    def test_9by16_tall_to_square(self):
        img = Image.new('RGB', (180, 320), color='cyan')
        result = fill_crop_image(img, 64, 64)
        self.assertEqual(result.size, (64, 64))


if __name__ == '__main__':
    unittest.main()
