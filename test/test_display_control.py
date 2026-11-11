import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

from modules.display_control import (
    get_pixel_mapper_config, get_matrix_dimensions,
    apply_exif_orientation, fill_crop_image, fit_image, process_image_for_display,
    get_image_fit_mode, get_image_fit_anchor,
    _parse_reported_size, _start_display_process
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


class TestFitImage(unittest.TestCase):
    """cover / contain / stretch plus the crop anchor."""

    TARGET = (192, 128)

    @staticmethod
    def _two_tone(size=(192, 400), top='blue', bottom='red', split=200):
        img = Image.new('RGB', size, bottom)
        img.paste(Image.new('RGB', (size[0], split), top), (0, 0))
        return img

    def test_cover_fills_the_canvas(self):
        img = Image.new('RGB', (400, 200), 'red')
        result = fit_image(img, *self.TARGET, mode='cover')
        self.assertEqual(result.size, self.TARGET)

    def test_cover_center_crops_equally(self):
        img = self._two_tone()
        result = fit_image(img, *self.TARGET, mode='cover', anchor='center')
        # 192x400 is narrowed vertically: the centre crop starts at y=136,
        # which is still inside the blue area (rows 0-199).
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(result.getpixel((0, 127)), (255, 0, 0))

    def test_cover_top_anchor_keeps_top(self):
        img = self._two_tone()
        result = fit_image(img, *self.TARGET, mode='cover', anchor='top')
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(result.getpixel((0, 127)), (0, 0, 255))

    def test_cover_bottom_anchor_keeps_bottom(self):
        img = self._two_tone()
        result = fit_image(img, *self.TARGET, mode='cover', anchor='bottom')
        self.assertEqual(result.getpixel((0, 0)), (255, 0, 0))

    def test_contain_letterboxes_with_background(self):
        img = Image.new('RGB', (400, 200), 'red')
        result = fit_image(img, *self.TARGET, mode='contain', anchor='center')
        self.assertEqual(result.size, self.TARGET)
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(result.getpixel((96, 64)), (255, 0, 0))

    def test_contain_top_anchor_aligns_to_top(self):
        img = Image.new('RGB', (400, 200), 'red')
        result = fit_image(img, *self.TARGET, mode='contain', anchor='top')
        self.assertEqual(result.getpixel((96, 0)), (255, 0, 0))
        self.assertEqual(result.getpixel((96, 127)), (0, 0, 0))

    def test_contain_left_anchor_aligns_left(self):
        img = Image.new('RGB', (100, 400), 'red')
        result = fit_image(img, *self.TARGET, mode='contain', anchor='left')
        self.assertEqual(result.getpixel((0, 64)), (255, 0, 0))
        self.assertEqual(result.getpixel((191, 64)), (0, 0, 0))

    def test_stretch_ignores_aspect_ratio(self):
        img = Image.new('RGB', (400, 200), 'red')
        result = fit_image(img, *self.TARGET, mode='stretch')
        self.assertEqual(result.size, self.TARGET)

    def test_unknown_mode_falls_back_to_cover(self):
        img = Image.new('RGB', (400, 200), 'red')
        result = fit_image(img, *self.TARGET, mode='nonsense')
        self.assertEqual(result.size, self.TARGET)

    def test_rgba_image_keeps_alpha(self):
        img = Image.new('RGBA', (400, 200), (255, 0, 0, 128))
        result = fit_image(img, *self.TARGET, mode='contain')
        self.assertEqual(result.mode, 'RGBA')
        self.assertEqual(result.size, self.TARGET)


class TestImageFitSettings(unittest.TestCase):

    def test_defaults(self):
        self.assertEqual(get_image_fit_mode({}), 'cover')
        self.assertEqual(get_image_fit_anchor({}), 'center')

    def test_values_are_read(self):
        self.assertEqual(
            get_image_fit_mode({'imageFitMode': 'Contain'}), 'contain')
        self.assertEqual(
            get_image_fit_anchor({'imageFitAnchor': 'top'}), 'top')

    def test_invalid_values_fall_back(self):
        self.assertEqual(get_image_fit_mode({'imageFitMode': 'zoom'}), 'cover')
        self.assertEqual(get_image_fit_anchor({'imageFitAnchor': 'middle'}),
                         'center')


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


class TestProcessImageTargetSize(unittest.TestCase):
    """Images must be prepared for the visible canvas, not the raw matrix.

    With a folding U-mapper the raw 384x64 matrix becomes a 192x128 canvas.
    Cropping images to the raw size made led-image-viewer fit them into the
    visible canvas preserving the aspect ratio, which left a thin strip of
    picture in the middle of the display.
    """

    SETTINGS = {
        'heightInPixel': '32',
        'widthInPixel': '32',
        'chainLength': '12',
        'parallelChains': '2',
        'direction': 'horizontal',
        'immichAutoOrientation': 'true',
    }

    def _processed_size(self, settings=None, source_size=(1000, 100), **kwargs):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = os.path.join(tmp_dir, 'source.png')
            Image.new('RGB', source_size, color='red').save(source)
            result = process_image_for_display(
                source, settings or dict(self.SETTINGS), **kwargs)
            try:
                with Image.open(result) as img:
                    return img.size
            finally:
                if result != source and os.path.exists(result):
                    os.remove(result)

    def test_umapper_uses_visible_canvas(self):
        self.assertEqual(self._processed_size(), (192, 128))

    def test_rotation_offset_uses_swapped_canvas(self):
        # The rotate feature adds an offset, which swaps the canvas axes.
        self.assertEqual(self._processed_size(width=128, height=192), (128, 192))

    def test_no_umapper_uses_raw_canvas(self):
        settings = dict(self.SETTINGS, parallelChains='1')
        self.assertEqual(self._processed_size(settings=settings), (384, 32))

    def test_portrait_source_is_cropped_not_letterboxed(self):
        self.assertEqual(
            self._processed_size(source_size=(200, 1200)), (192, 128)
        )


class TestProcessImageFitSettings(unittest.TestCase):
    """The imageFitMode/Anchor settings control the preprocessing result."""

    SETTINGS = {
        'heightInPixel': '32',
        'widthInPixel': '32',
        'chainLength': '12',
        'parallelChains': '2',
        'direction': 'horizontal',
        'immichAutoOrientation': 'true',
    }

    def _process(self, source, **overrides):
        settings = dict(self.SETTINGS)
        settings.update(overrides)
        return process_image_for_display(source, settings)

    def test_contain_letterboxes_wide_picture(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'wide.png')
            Image.new('RGB', (400, 200), 'red').save(source)
            result = self._process(source, imageFitMode='contain')
            try:
                with Image.open(result) as img:
                    self.assertEqual(img.size, (192, 128))
                    rgb = img.convert('RGB')
                    self.assertEqual(rgb.getpixel((0, 0)), (0, 0, 0))
                    self.assertEqual(rgb.getpixel((96, 64)), (255, 0, 0))
            finally:
                if result != source and os.path.exists(result):
                    os.remove(result)

    def test_cover_has_no_black_bars(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'wide.png')
            Image.new('RGB', (400, 200), 'red').save(source)
            result = self._process(source, imageFitMode='cover')
            try:
                with Image.open(result) as img:
                    rgb = img.convert('RGB')
                    self.assertEqual(rgb.getpixel((0, 0)), (255, 0, 0))
                    self.assertEqual(rgb.getpixel((0, 127)), (255, 0, 0))
            finally:
                if result != source and os.path.exists(result):
                    os.remove(result)

    def test_gif_frames_use_the_fit_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, 'anim.gif')
            frames = [Image.new('RGB', (400, 200), 'red'),
                      Image.new('RGB', (400, 200), 'blue')]
            frames[0].save(source, save_all=True, append_images=frames[1:],
                           duration=100, loop=0)
            result = self._process(source, imageFitMode='contain')
            try:
                with Image.open(result) as img:
                    self.assertEqual(img.size, (192, 128))
                    img.seek(0)
                    rgb = img.convert('RGB')
                    # Letterboxed: the top row is background, not picture.
                    self.assertEqual(rgb.getpixel((0, 0)), (0, 0, 0))
                    self.assertEqual(rgb.getpixel((96, 64)), (255, 0, 0))
            finally:
                if result != source and os.path.exists(result):
                    os.remove(result)


class TestParseReportedSize(unittest.TestCase):

    def test_parses_viewer_output(self):
        line = ("Size: 192x128. Hardware gpio mapping: adafruit-hat\n"
                "Loading 1 files...")
        self.assertEqual(_parse_reported_size(line), (192, 128))

    def test_returns_none_without_size(self):
        self.assertIsNone(_parse_reported_size("Loading 1 files..."))
        self.assertIsNone(_parse_reported_size(""))


class TestStartDisplayProcess(unittest.TestCase):
    """Regression tests for the brightness/slowdown settings parsing.

    These call sites previously passed (value, default) instead of
    (settings, key, default), which raised a TypeError before any display
    process could start.
    """

    BASE_SETTINGS = {
        'heightInPixel': '32',
        'widthInPixel': '32',
        'chainLength': '12',
        'parallelChains': '2',
        'direction': 'horizontal',
        'displayBrightness': '100',
        'ledSlowdown': '2',
    }

    def _run(self, settings):
        with patch('modules.display_control.Thread'), \
                patch('modules.display_control.subprocess.Popen') as mock_popen, \
                patch('modules.display_control.process_image_for_display',
                      return_value='/tmp/processed.png'), \
                patch('modules.display_control.stopProcess'), \
                patch('modules.display_control.read_settings', return_value=settings):
            _start_display_process('photo.png', 'displayImage', 'static/pictures')
        return mock_popen.call_args[0][0]

    def test_display_image_uses_brightness_and_slowdown(self):
        cmd = self._run(dict(self.BASE_SETTINGS))
        self.assertIn('--led-brightness=100', cmd)
        self.assertIn('--led-slowdown-gpio=2', cmd)

    def test_invalid_numeric_settings_fall_back_to_defaults(self):
        settings = dict(
            self.BASE_SETTINGS,
            displayBrightness='not-a-number',
            ledSlowdown=None,
        )
        cmd = self._run(settings)
        self.assertIn('--led-brightness=100', cmd)
        self.assertIn('--led-slowdown-gpio=2', cmd)

    def test_demo_uses_parsed_settings(self):
        settings = dict(
            self.BASE_SETTINGS,
            displayBrightness='40',
            ledSlowdown='3',
        )
        with patch('modules.display_control.Thread'), \
                patch('modules.display_control.subprocess.Popen') as mock_popen, \
                patch('modules.display_control.stopProcess'), \
                patch('modules.display_control.read_settings', return_value=settings):
            _start_display_process(1, 'displayDemo', 'static/pictures')
        cmd = mock_popen.call_args[0][0]
        self.assertIn('--led-brightness=40', cmd)
        self.assertIn('--led-slowdown-gpio=3', cmd)

    def _capture_process_mock(self, rotation_offset=0):
        with patch('modules.display_control.Thread'), \
                patch('modules.display_control.subprocess.Popen'), \
                patch('modules.display_control.process_image_for_display',
                      return_value='/tmp/processed.png') as mock_process, \
                patch('modules.display_control.stopProcess'), \
                patch('modules.display_control.read_settings',
                      return_value=dict(self.BASE_SETTINGS)):
            _start_display_process('photo.png', 'displayImage',
                                   'static/pictures', rotation_offset)
        return mock_process

    def test_image_is_sized_for_visible_canvas(self):
        _, kwargs = self._capture_process_mock().call_args
        self.assertEqual((kwargs['width'], kwargs['height']), (192, 128))

    def test_image_is_sized_for_rotated_canvas(self):
        _, kwargs = self._capture_process_mock(rotation_offset=90).call_args
        self.assertEqual((kwargs['width'], kwargs['height']), (128, 192))


if __name__ == '__main__':
    unittest.main()
