import json
import os
import tempfile
import unittest

from modules.layout_handler import (
    default_layout,
    grid_dimensions,
    read_layout,
    save_layout,
    validate_layout,
    new_widget,
    WIDGET_TYPES,
)

# A geometry dict shaped like modules.geometry.get_display_geometry() output.
GEOMETRY_384x64 = {
    "width": 384,
    "height": 64,
    "rawWidth": 384,
    "rawHeight": 64,
    "cellW": 32,
    "cellH": 32,
    "cols": 12,
    "rows": 2,
    "rotation": 0,
    "pixelMapper": "Rotate:0",
}

# U-mapper + Rotate:180 for the default 32x32, 12 chained, 2 parallel setup.
GEOMETRY_192x128 = {
    "width": 192,
    "height": 128,
    "rawWidth": 384,
    "rawHeight": 64,
    "cellW": 32,
    "cellH": 32,
    "cols": 6,
    "rows": 4,
    "rotation": 180,
    "pixelMapper": "U-mapper;Rotate:180",
}


class TestDefaultLayout(unittest.TestCase):

    def test_has_expected_keys(self):
        layout = default_layout()
        self.assertIn("enabled", layout)
        self.assertIn("grid", layout)
        self.assertIn("widgets", layout)
        self.assertEqual(layout["widgets"], [])

    def test_grid_has_no_display_geometry(self):
        # The grid size is derived from settings.json, never stored.
        layout = default_layout()
        self.assertNotIn("cellW", layout["grid"])
        self.assertNotIn("cellH", layout["grid"])

    def test_default_layout_is_a_copy(self):
        first = default_layout()
        first["grid"]["showBorders"] = True
        self.assertFalse(default_layout()["grid"]["showBorders"])


class TestGridDimensions(unittest.TestCase):

    def test_standard_panel_grid(self):
        cols, rows, cw, ch = grid_dimensions(GEOMETRY_384x64)
        self.assertEqual((cols, rows, cw, ch), (12, 2, 32, 32))

    def test_umapper_grid(self):
        cols, rows, cw, ch = grid_dimensions(GEOMETRY_192x128)
        self.assertEqual((cols, rows, cw, ch), (6, 4, 32, 32))

    def test_finer_grid(self):
        geometry = dict(GEOMETRY_384x64, cellW=16, cellH=16, cols=24, rows=4)
        cols, rows, cw, ch = grid_dimensions(geometry)
        self.assertEqual((cols, rows, cw, ch), (24, 4, 16, 16))


class TestReadWrite(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.tmp.close()

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.remove(self.tmp.name)

    def test_read_missing_returns_default(self):
        missing = self.tmp.name + ".missing"
        layout = read_layout(missing)
        self.assertNotIn("cellW", layout["grid"])
        self.assertEqual(layout["widgets"], [])

    def test_read_invalid_json_returns_default(self):
        with open(self.tmp.name, "w") as handle:
            handle.write("{not valid json")
        layout = read_layout(self.tmp.name)
        self.assertEqual(layout["widgets"], [])

    def test_roundtrip(self):
        layout = default_layout()
        layout["widgets"].append(new_widget("clock"))
        self.assertTrue(save_layout(layout, self.tmp.name))
        loaded = read_layout(self.tmp.name)
        self.assertEqual(len(loaded["widgets"]), 1)
        self.assertEqual(loaded["widgets"][0]["type"], "clock")

    def test_legacy_cell_keys_are_ignored(self):
        with open(self.tmp.name, "w") as handle:
            json.dump({"grid": {"cellW": 16, "cellH": 16, "showBorders": True}}, handle)
        layout = read_layout(self.tmp.name)
        self.assertNotIn("cellW", layout["grid"])
        self.assertNotIn("cellH", layout["grid"])
        self.assertTrue(layout["grid"]["showBorders"])

    def test_read_normalizes_grid_colors(self):
        with open(self.tmp.name, "w") as handle:
            json.dump({"grid": {"borderColor": [300, -5, 12]}}, handle)
        layout = read_layout(self.tmp.name)
        self.assertEqual(layout["grid"]["borderColor"], [255, 0, 12])


class TestValidateLayout(unittest.TestCase):

    def _base(self):
        layout = default_layout()
        layout["widgets"] = [
            {
                "id": "a",
                "type": "clock",
                "col": 0,
                "row": 0,
                "w": 2,
                "h": 1,
                "style": {"color": [300, -10, 12]},
                "config": {},
            }
        ]
        return layout

    def test_valid_layout_has_no_errors(self):
        normalized, errors = validate_layout(self._base(), GEOMETRY_384x64)
        self.assertEqual(errors, [])
        self.assertEqual(len(normalized["widgets"]), 1)

    def test_color_is_clamped(self):
        normalized, errors = validate_layout(self._base(), GEOMETRY_384x64)
        self.assertEqual(errors, [])
        self.assertEqual(normalized["widgets"][0]["style"]["color"], [255, 0, 12])

    def test_unknown_type_rejected(self):
        layout = self._base()
        layout["widgets"][0]["type"] = "does_not_exist"
        _normalized, errors = validate_layout(layout, GEOMETRY_384x64)
        self.assertTrue(any("unknown type" in error for error in errors))

    def test_out_of_bounds_is_clamped_to_geometry(self):
        layout = self._base()
        layout["widgets"][0].update({"col": 50, "row": 50, "w": 2, "h": 1})
        normalized, errors = validate_layout(layout, GEOMETRY_192x128)
        self.assertEqual(errors, [])
        widget = normalized["widgets"][0]
        self.assertLessEqual(widget["col"] + widget["w"], 6)
        self.assertLessEqual(widget["row"] + widget["h"], 4)

    def test_overlap_rejected(self):
        layout = self._base()
        layout["widgets"].append(
            {
                "id": "b",
                "type": "static_text",
                "col": 1,
                "row": 0,
                "w": 2,
                "h": 1,
                "style": {},
                "config": {},
            }
        )
        _normalized, errors = validate_layout(layout, GEOMETRY_384x64)
        self.assertTrue(any("overlaps" in error for error in errors))

    def test_legacy_cell_keys_are_dropped(self):
        layout = self._base()
        layout["grid"]["cellW"] = 16
        layout["grid"]["cellH"] = 16
        normalized, errors = validate_layout(layout, GEOMETRY_384x64)
        self.assertEqual(errors, [])
        self.assertNotIn("cellW", normalized["grid"])
        self.assertNotIn("cellH", normalized["grid"])

    def test_missing_id_is_generated(self):
        layout = self._base()
        del layout["widgets"][0]["id"]
        normalized, errors = validate_layout(layout, GEOMETRY_384x64)
        self.assertEqual(errors, [])
        self.assertTrue(normalized["widgets"][0]["id"])


class TestNewWidget(unittest.TestCase):

    def test_all_types_have_defaults(self):
        for widget_type in WIDGET_TYPES:
            widget = new_widget(widget_type)
            self.assertEqual(widget["type"], widget_type)
            self.assertIn("style", widget)
            self.assertIn("config", widget)
            self.assertTrue(widget["id"])

    def test_widget_ids_are_unique(self):
        ids = {new_widget("clock")["id"] for _ in range(20)}
        self.assertEqual(len(ids), 20)


if __name__ == "__main__":
    unittest.main()
