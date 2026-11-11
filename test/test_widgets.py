import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, PropertyMock, patch

from PIL import Image

from modules.layout_handler import default_layout
from modules.surface import Surface, font_path_for_height
from modules.widgets import WidgetContext
from modules.widgets.api_text import (
    ApiTextWidget,
    extract_by_regex,
    extract_json_path,
    format_value,
)
from modules.widgets.clock import ClockWidget
from modules.widgets.days_until import DaysUntilWidget, resolve_target
from modules.widgets.image import ImageWidget, _is_safe_filename
from modules.widgets.static_text import StaticTextWidget


def make_context(settings=None, layout=None, width=384, height=64):
    return WidgetContext(
        settings or {"timezone": "UTC"},
        layout or default_layout(),
        width=width,
        height=height,
    )


def spec(widget_type, config=None, style=None, col=0, row=0, w=2, h=1):
    return {
        "id": "test",
        "type": widget_type,
        "col": col,
        "row": row,
        "w": w,
        "h": h,
        "style": style or {},
        "config": config or {},
    }


class TestResolveTarget(unittest.TestCase):

    def test_days_until_christmas(self):
        days, target = resolve_target(date(2026, 11, 10), 12, 25)
        self.assertEqual(days, 45)
        self.assertEqual(target, date(2026, 12, 25))

    def test_on_the_day_is_zero(self):
        days, target = resolve_target(date(2026, 12, 25), 12, 25)
        self.assertEqual(days, 0)
        self.assertEqual(target, date(2026, 12, 25))

    def test_passed_date_rolls_to_next_year(self):
        days, target = resolve_target(date(2026, 12, 26), 12, 25)
        self.assertEqual(target, date(2027, 12, 25))
        self.assertEqual(days, 364)

    def test_explicit_year_in_past_is_negative(self):
        days, target = resolve_target(date(2026, 1, 1), 12, 25, year=2025)
        self.assertLess(days, 0)
        self.assertEqual(target, date(2025, 12, 25))

    def test_invalid_date_returns_none(self):
        days, target = resolve_target(date(2026, 1, 1), 2, 30)
        self.assertIsNone(days)
        self.assertIsNone(target)


class TestDaysUntilWidget(unittest.TestCase):

    def test_build_text_template(self):
        widget = DaysUntilWidget(
            spec("days_until", {"month": 12, "day": 25, "label": "XMAS"}),
            make_context(),
        )
        self.assertEqual(widget.build_text(date(2026, 11, 10)), "45d XMAS")

    def test_build_text_finished_text_on_the_day(self):
        widget = DaysUntilWidget(
            spec(
                "days_until",
                {"month": 12, "day": 25, "label": "XMAS", "finishedText": "MERRY XMAS"},
            ),
            make_context(),
        )
        self.assertEqual(widget.build_text(date(2026, 12, 25)), "MERRY XMAS")

    def test_build_text_invalid_date(self):
        widget = DaysUntilWidget(
            spec("days_until", {"month": 2, "day": 30}), make_context()
        )
        self.assertEqual(widget.build_text(date(2026, 1, 1)), "--")


class TestClockWidget(unittest.TestCase):

    def test_render_produces_pixels(self):
        widget = ClockWidget(
            spec("clock", {"timeFormat": "%H:%M", "dateFormat": "%d"}),
            make_context(),
        )
        timestamp = datetime(2026, 1, 1, 12, 34, tzinfo=timezone.utc).timestamp()
        widget.update(timestamp)
        surface = Surface(96, 32)
        widget.render(surface, (0, 0, 96, 32))
        self.assertIsNotNone(surface.image.getbbox())


class TestStaticTextWidget(unittest.TestCase):

    def test_static_text_renders(self):
        widget = StaticTextWidget(
            spec("static_text", {"text": "Hello", "scroll": False}),
            make_context(),
        )
        widget.update(0)
        surface = Surface(96, 16)
        widget.render(surface, (0, 0, 96, 16))
        self.assertIsNotNone(surface.image.getbbox())

    def test_scrolling_text_renders(self):
        widget = StaticTextWidget(
            spec("static_text", {"text": "A long scrolling text", "scroll": True, "speed": 20}),
            make_context(),
        )
        widget.update(1.0)
        surface = Surface(64, 16)
        widget.render(surface, (0, 0, 64, 16))
        self.assertIsNotNone(surface.image.getbbox())


class TestApiTextHelpers(unittest.TestCase):

    def test_extract_json_path_nested(self):
        data = {"main": {"temp": 21.5, "feels_like": 20}, "items": [{"name": "a"}]}
        self.assertEqual(extract_json_path(data, "main.temp"), 21.5)
        self.assertEqual(extract_json_path(data, "items.0.name"), "a")
        self.assertIsNone(extract_json_path(data, "main.missing"))

    def test_extract_json_path_empty(self):
        self.assertIsNone(extract_json_path({"a": 1}, ""))

    def test_extract_by_regex_group(self):
        self.assertEqual(extract_by_regex("temp=23C", r"temp=(\d+)"), "23")

    def test_extract_by_regex_no_match(self):
        self.assertIsNone(extract_by_regex("abc", r"\d+"))

    def test_extract_by_regex_invalid(self):
        self.assertIsNone(extract_by_regex("abc", r"("))

    def test_format_value_integer(self):
        self.assertEqual(format_value(21.6), "22")

    def test_format_value_decimals(self):
        self.assertEqual(format_value(21.54, 1), "21.5")

    def test_format_value_bool(self):
        self.assertEqual(format_value(True), "on")
        self.assertEqual(format_value(False), "off")

    def test_format_value_none(self):
        self.assertEqual(format_value(None), "")


class TestApiTextWidget(unittest.TestCase):

    def test_invalid_url_does_not_fetch(self):
        widget = ApiTextWidget(spec("api_text", {"url": ""}), make_context())
        widget.start()
        self.assertIsNone(widget.fetch_once())
        widget.stop()

    @patch("modules.widgets.api_text.requests.request")
    def test_fetch_json_value(self, mock_request):
        response = MagicMock()
        response.json.return_value = {"main": {"temp": 21.54}}
        response.text = ""
        mock_request.return_value = response

        widget = ApiTextWidget(
            spec(
                "api_text",
                {"url": "https://example.com/weather", "jsonPath": "main.temp", "decimals": 1},
            ),
            make_context(),
        )
        self.assertEqual(widget.fetch_once(), "21.5")

    @patch("modules.widgets.api_text.requests.request")
    def test_fetch_plain_text(self, mock_request):
        response = MagicMock()
        response.text = "  hello world  "
        mock_request.return_value = response

        widget = ApiTextWidget(
            spec("api_text", {"url": "https://example.com/text"}), make_context()
        )
        self.assertEqual(widget.fetch_once(), "hello world")

    def test_render_shows_error_text_when_no_value(self):
        widget = ApiTextWidget(
            spec("api_text", {"url": "", "errorText": "N/A"}),
            make_context(),
        )
        surface = Surface(32, 16)
        widget.render(surface, (0, 0, 32, 16))
        self.assertIsNotNone(surface.image.getbbox())


class TestImageWidget(unittest.TestCase):

    def test_safe_filename(self):
        self.assertTrue(_is_safe_filename("photo.png"))
        self.assertFalse(_is_safe_filename("../photo.png"))
        self.assertFalse(_is_safe_filename("sub/photo.png"))
        self.assertFalse(_is_safe_filename(""))

    def test_unsafe_filename_has_no_path(self):
        widget = ImageWidget(
            spec("image", {"filename": "../evil.png"}), make_context()
        )
        self.assertIsNone(widget._path())

    def test_render_with_missing_file_does_not_crash(self):
        widget = ImageWidget(
            spec("image", {"filename": "does-not-exist.png"}), make_context()
        )
        surface = Surface(32, 32)
        widget.render(surface, (0, 0, 32, 32))
        self.assertIsNone(surface.image.getbbox())


class TestAnimatedImageWidget(unittest.TestCase):
    """GIF playback in the grid: frames, timing, looping and scaling."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = self._tmp.name
        patcher = patch.object(WidgetContext, 'static_pictures_dir',
                               new_callable=PropertyMock,
                               return_value=self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _make_gif(self, colours, size=(40, 40), duration=100,
                  name='anim.gif'):
        frames = [Image.new('RGB', size, colour) for colour in colours]
        path = os.path.join(self.folder, name)
        frames[0].save(path, save_all=True, append_images=frames[1:],
                       duration=duration, loop=0)
        return path

    def _widget(self, filename='anim.gif', fit='cover'):
        return ImageWidget(
            spec('image', {'filename': filename}, style={'fit': fit}),
            make_context())

    def _render(self, widget, now, rect=(0, 0, 32, 32), canvas=(48, 48)):
        widget.update(now)
        surface = Surface(*canvas)
        widget.render(surface, rect)
        return surface

    def test_frames_advance_and_loop(self):
        self._make_gif([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        widget = self._widget()
        self.assertEqual(self._render(widget, 100.0).image.getpixel((0, 0)),
                         (255, 0, 0))
        self.assertEqual(self._render(widget, 100.15).image.getpixel((0, 0)),
                         (0, 255, 0))
        self.assertEqual(self._render(widget, 100.25).image.getpixel((0, 0)),
                         (0, 0, 255))
        # After the last frame the animation restarts.
        self.assertEqual(self._render(widget, 100.35).image.getpixel((0, 0)),
                         (255, 0, 0))

    def test_frames_are_scaled_to_the_widget_rect_only(self):
        self._make_gif([(255, 0, 0), (0, 255, 0)])
        widget = self._widget()
        surface = self._render(widget, 100.0, rect=(0, 0, 16, 16))
        self.assertEqual(surface.image.getpixel((0, 0)), (255, 0, 0))
        # Everything outside the widget rectangle stays black.
        self.assertEqual(surface.image.getpixel((20, 20)), (0, 0, 0))

    def test_contain_letterboxes_into_the_rect(self):
        self._make_gif([(255, 0, 0)], size=(40, 20))
        widget = self._widget(fit='contain')
        surface = self._render(widget, 100.0, rect=(0, 0, 32, 32))
        # A wide picture is letterboxed: the red band sits at the top, the
        # rest of the rectangle stays black.
        self.assertEqual(surface.image.getpixel((16, 0)), (255, 0, 0))
        self.assertEqual(surface.image.getpixel((16, 30)), (0, 0, 0))

    def test_still_image_still_renders(self):
        Image.new('RGB', (40, 40), (10, 20, 30)).save(
            os.path.join(self.folder, 'still.png'))
        widget = self._widget(filename='still.png')
        self.assertEqual(self._render(widget, 100.0).image.getpixel((0, 0)),
                         (10, 20, 30))

    def test_frame_count_is_capped(self):
        self._make_gif([(i, 0, 0) for i in range(8)], duration=100)
        with patch('modules.widgets.image.MAX_FRAMES', 2):
            widget = self._widget()
            self._render(widget, 100.0)
            frames = len(widget._frames)
            total = widget._total_ms
        self.assertEqual(frames, 2)
        # Dropped frames keep the original timing (8 frames * 100 ms).
        self.assertEqual(total, 800)

    def test_file_change_reloads_the_frames(self):
        self._make_gif([(255, 0, 0), (0, 255, 0)])
        widget = self._widget()
        self._render(widget, 100.0)
        self._make_gif([(0, 0, 255), (255, 255, 0)])
        os.utime(os.path.join(self.folder, 'anim.gif'),
                 (1000000000, 1000000000))
        self.assertEqual(self._render(widget, 200.0, canvas=(48, 48))
                         .image.getpixel((0, 0)), (0, 0, 255))

    def test_stop_releases_the_frames(self):
        self._make_gif([(255, 0, 0)])
        widget = self._widget()
        self._render(widget, 100.0)
        widget.stop()
        self.assertIsNone(widget._frames)


class TestSurface(unittest.TestCase):

    def test_font_selection_prefers_largest_fitting(self):
        _path, height = font_path_for_height(14)
        self.assertEqual(height, 13)
        _path, height = font_path_for_height(32)
        self.assertEqual(height, 20)
        _path, height = font_path_for_height(2)
        self.assertEqual(height, 6)

    def test_draw_text_is_clipped(self):
        surface = Surface(16, 8)
        font = __import__("modules.surface", fromlist=["load_font"]).load_font(8)
        surface.draw_text(0, 0, 16, 8, "WWWWWWWWWWWW", (255, 255, 255), font)
        # Nothing outside the 16x8 area can be drawn, image size stays fixed.
        self.assertEqual(surface.image.size, (16, 8))
        self.assertIsNotNone(surface.image.getbbox())

    def test_draw_image(self):
        surface = Surface(16, 16)
        image = Image.new("RGB", (8, 8), (255, 0, 0))
        surface.draw_image(image, 0, 0, 16, 16)
        self.assertIsNotNone(surface.image.getbbox())


if __name__ == "__main__":
    unittest.main()
