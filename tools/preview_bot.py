#!/usr/bin/env python3
"""Render contact sheets for every bot face style and mood.

This is the visual iteration tool for the face engine: it needs no hardware and
writes plain PNGs that can be inspected on any machine.

Usage:
    python3 tools/preview_bot.py
    python3 tools/preview_bot.py --out /tmp/bot --sizes 32x32,64x32,128x64
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.bot.face import MOOD_NAMES, FaceModel
from modules.bot.render import available_styles, render_face


def parse_size(value):
    try:
        width, height = value.lower().split("x", 1)
        return int(width), int(height)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(f"invalid size {value!r}, use WIDTHxHEIGHT")


def render_tile(width, height, style, mood, options):
    model = FaceModel(mood=mood, animations=False)
    model.update(0.0)
    face = render_face(
        width, height, model.snapshot(), style=style, options=options,
    )
    background = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    background.alpha_composite(face)
    return background.convert("RGB")


def build_sheet(width, height, styles, moods, options):
    scale = max(1, 192 // max(width, height))
    tile_width = width * scale
    tile_height = height * scale
    padding = 12
    label_width = 96
    header_height = 18
    footer_height = 16

    sheet_width = label_width + len(moods) * (tile_width + padding) + padding
    sheet_height = (
        header_height + len(styles) * (tile_height + footer_height + padding)
        + padding
    )

    sheet = Image.new("RGB", (sheet_width, sheet_height), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for column, mood in enumerate(moods):
        x = label_width + column * (tile_width + padding)
        draw.text((x, 4), mood.upper(), fill=(210, 210, 210), font=font)

    for row, style in enumerate(styles):
        y = header_height + row * (tile_height + footer_height + padding)
        draw.text((6, y + tile_height // 2 - 6), style, fill=(210, 210, 210),
                  font=font)
        for column, mood in enumerate(moods):
            x = label_width + column * (tile_width + padding)
            tile = render_tile(width, height, style, mood, options)
            if scale != 1:
                tile = tile.resize((tile_width, tile_height), Image.Resampling.NEAREST)
            sheet.paste(tile, (x, y))
            draw.text((x, y + tile_height + 2), mood, fill=(140, 140, 140),
                      font=font)

    return sheet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=os.path.join(PROJECT_ROOT, "preview"),
        help="output directory (default: preview/)",
    )
    parser.add_argument(
        "--sizes", default="32x32,64x32,128x64,256x128",
        help="comma separated WIDTHxHEIGHT list",
    )
    parser.add_argument(
        "--styles", default=",".join(available_styles()),
        help="comma separated style ids",
    )
    parser.add_argument(
        "--moods", default=",".join(MOOD_NAMES),
        help="comma separated mood names",
    )
    parser.add_argument("--color", default=None, help="robot eye colour")
    parser.add_argument("--accent", default=None, help="robot accent colour")
    args = parser.parse_args(argv)

    sizes = [parse_size(value) for value in args.sizes.split(",") if value]
    styles = [value for value in args.styles.split(",") if value]
    moods = [value for value in args.moods.split(",") if value]

    unknown = [style for style in styles if style not in available_styles()]
    if unknown:
        parser.error(f"unknown style(s): {', '.join(unknown)}")
    unknown = [mood for mood in moods if mood not in MOOD_NAMES]
    if unknown:
        parser.error(f"unknown mood(s): {', '.join(unknown)}")

    options = {}
    if args.color:
        options["color"] = args.color
    if args.accent:
        options["accent"] = args.accent

    os.makedirs(args.out, exist_ok=True)
    for width, height in sizes:
        sheet = build_sheet(width, height, styles, moods, options)
        path = os.path.join(args.out, f"bot_{width}x{height}.png")
        sheet.save(path)
        print(path)


if __name__ == "__main__":
    main()
