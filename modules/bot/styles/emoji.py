# modules/bot/styles/emoji.py
"""Minimal black-and-white emoji face.

The face is a white disc with pure black features. No colours and no grey
values are used, which keeps it readable on a 32x32 panel and makes the style
easy to verify in tests.
"""
import math

from .base import StyleCanvas

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


class EmojiStyle:
    id = "emoji"
    label = "Minimal B&W"

    def render(self, width, height, face, options=None, background=None):
        canvas = StyleCanvas(width, height, background=background)
        dy = face.bob * 1.2

        # Filled disc: the visual anchor of the minimal style.
        canvas.circle(16, 16 + dy, 14, WHITE)

        self._draw_brows(canvas, face, dy)
        self._draw_eye(canvas, 10.5, 14.5 + dy, face.eye_left)
        self._draw_eye(canvas, 21.5, 14.5 + dy, face.eye_right)
        self._draw_mouth(canvas, face, dy)

        return canvas.image

    @staticmethod
    def _draw_eye(canvas, cx, cy, openness):
        half_height = 2.9 * max(0.05, openness)
        if openness < 0.12:
            canvas.line(cx - 2.2, cy, cx + 2.2, cy, BLACK, width=1.8)
            return
        canvas.ellipse(cx, cy, 2.2, half_height, BLACK)

    @staticmethod
    def _draw_brows(canvas, face, dy):
        if abs(face.brow_tilt) < 0.05 and abs(face.brow_raise) < 0.05:
            return

        base = 8.8 + dy - face.brow_raise * 1.5
        inner = base - face.brow_tilt * 1.0
        outer = base + face.brow_tilt * 0.3
        canvas.line(7.5, outer, 12.5, inner, BLACK, width=1.3)
        canvas.line(24.5, outer, 19.5, inner, BLACK, width=1.3)

    @staticmethod
    def _draw_mouth(canvas, face, dy):
        center_y = 21.2 + dy
        width = 4.0 + face.mouth_width * 8.0

        if face.mouth_open > 0.12:
            height = 2.0 + face.mouth_open * 4.4
            x0 = 16 - width / 2
            x1 = 16 + width / 2
            y0 = center_y - height / 2
            y1 = center_y + height / 2
            if face.mouth_curve >= 0:
                canvas.pieslice(x0, y0, x1, y1, 0, 180, BLACK)
            else:
                canvas.pieslice(x0, y0, x1, y1, 180, 360, BLACK)
            return

        points = []
        for index in range(9):
            t = index / 8.0
            x = 16 - width / 2 + width * t
            y = center_y + face.mouth_curve * 3.0 * math.sin(math.pi * t)
            points.append((x, y))
        canvas.polyline(points, BLACK, width=1.6)
