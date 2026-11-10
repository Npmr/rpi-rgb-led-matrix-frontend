import unittest

from modules.geometry import (
    get_base_rotation,
    get_display_geometry,
    get_matrix_dimensions,
    get_pixel_mapper_config,
)


def settings(**overrides):
    base = {
        "widthInPixel": "32",
        "heightInPixel": "32",
        "direction": "horizontal",
        "chainLength": "12",
        "parallelChains": "2",
    }
    base.update(overrides)
    return base


class TestBaseRotation(unittest.TestCase):

    def test_directional_rotations(self):
        self.assertEqual(get_base_rotation({"direction": "horizontal"}), 180)
        self.assertEqual(get_base_rotation({"direction": "vertical"}), 270)
        self.assertEqual(get_base_rotation({"direction": "verticalTurned"}), 90)
        self.assertEqual(get_base_rotation({"direction": "horizontalTurned"}), 0)

    def test_unknown_direction_defaults_to_270(self):
        self.assertEqual(get_base_rotation({"direction": "other"}), 270)
        self.assertEqual(get_base_rotation({}), 270)


class TestPixelMapper(unittest.TestCase):

    def test_single_chain_has_no_umapper(self):
        mapper = get_pixel_mapper_config(
            {"parallelChains": 1, "chainLength": 1}, 180
        )
        self.assertEqual(mapper, "Rotate:180")

    def test_umapper_for_parallel_even_chain(self):
        mapper = get_pixel_mapper_config(
            {"parallelChains": 2, "chainLength": 12}, 180
        )
        self.assertEqual(mapper, "U-mapper;Rotate:180")

    def test_umapper_requires_even_chain(self):
        mapper = get_pixel_mapper_config(
            {"parallelChains": 2, "chainLength": 5}, 180
        )
        self.assertEqual(mapper, "Rotate:180")

    def test_umapper_requires_min_chain(self):
        mapper = get_pixel_mapper_config(
            {"parallelChains": 2, "chainLength": 2}, 180
        )
        self.assertEqual(mapper, "Rotate:180")


class TestMatrixDimensions(unittest.TestCase):

    def test_raw_dimensions(self):
        self.assertEqual(get_matrix_dimensions(settings()), (384, 64))

    def test_missing_keys_have_defaults(self):
        self.assertEqual(get_matrix_dimensions({}), (32, 32))


class TestDisplayGeometry(unittest.TestCase):

    def test_umapper_visible_canvas(self):
        geometry = get_display_geometry(settings())
        self.assertEqual(geometry["rawWidth"], 384)
        self.assertEqual(geometry["rawHeight"], 64)
        self.assertEqual(geometry["width"], 192)
        self.assertEqual(geometry["height"], 128)
        self.assertEqual(geometry["cellW"], 32)
        self.assertEqual(geometry["cellH"], 32)
        self.assertEqual(geometry["cols"], 6)
        self.assertEqual(geometry["rows"], 4)
        self.assertEqual(geometry["rotation"], 180)
        self.assertEqual(geometry["pixelMapper"], "U-mapper;Rotate:180")

    def test_no_umapper_uses_raw_canvas(self):
        geometry = get_display_geometry(
            settings(parallelChains="1", chainLength="12")
        )
        self.assertEqual(geometry["width"], 384)
        self.assertEqual(geometry["height"], 32)
        self.assertEqual(geometry["cols"], 12)
        self.assertEqual(geometry["rows"], 1)
        self.assertNotIn("U-mapper", geometry["pixelMapper"])

    def test_rotation_90_270_swaps_axes_and_cells(self):
        geometry = get_display_geometry(
            settings(
                widthInPixel="64",
                heightInPixel="32",
                chainLength="4",
                parallelChains="1",
                direction="vertical",  # rotation 270
            )
        )
        self.assertEqual(geometry["rotation"], 270)
        self.assertEqual(geometry["rawWidth"], 256)
        self.assertEqual(geometry["rawHeight"], 32)
        # Axes swapped by the rotation mapper.
        self.assertEqual(geometry["width"], 32)
        self.assertEqual(geometry["height"], 256)
        # Cell size swaps too for non-square panels.
        self.assertEqual(geometry["cellW"], 32)
        self.assertEqual(geometry["cellH"], 64)
        self.assertEqual(geometry["cols"], 1)
        self.assertEqual(geometry["rows"], 4)

    def test_rotation_0_keeps_axes(self):
        geometry = get_display_geometry(
            settings(direction="horizontalTurned", chainLength="4", parallelChains="1")
        )
        self.assertEqual(geometry["rotation"], 0)
        self.assertEqual(geometry["width"], 128)
        self.assertEqual(geometry["height"], 32)
        self.assertEqual(geometry["cols"], 4)
        self.assertEqual(geometry["rows"], 1)

    def test_grid_never_zero(self):
        geometry = get_display_geometry(
            settings(widthInPixel="1000", heightInPixel="1000")
        )
        self.assertGreaterEqual(geometry["cols"], 1)
        self.assertGreaterEqual(geometry["rows"], 1)

    def test_invalid_settings_fall_back_to_defaults(self):
        geometry = get_display_geometry(
            {"widthInPixel": "nope", "heightInPixel": None, "chainLength": "x"}
        )
        self.assertGreaterEqual(geometry["width"], 1)
        self.assertGreaterEqual(geometry["height"], 1)


if __name__ == "__main__":
    unittest.main()
