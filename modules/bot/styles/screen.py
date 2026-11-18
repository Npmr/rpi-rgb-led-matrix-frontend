# modules/bot/styles/screen.py
"""Screen face: only two eyes and a mouth on a transparent background.

This is the minimal "black screen" look: white rounded-rectangle eyes and a
small smile, with nothing else drawn. The transparent tile works both over a
black full-screen canvas and over the grid background.
"""
import math

from .base import StyleCanvas

WHITE = (255, 255, 255)


class ScreenStyle:
    id = "screen"
    label = "Screen face"

    def render(self, width, height, face, options=None, background=None):
        canvas = StyleCanvas(width, height, background=background)
        dy = face.bob * 1.2
        gaze_x = face.gaze_x * 1.2
        gaze_y = face.gaze_y * 0.8

        self._draw_eye(
            canvas, 9.0 + gaze_x, 14.5 + dy + gaze_y, face.eye_left
        )
        self._draw_eye(
            canvas, 23.0 + gaze_x, 14.5 + dy + gaze_y, face.eye_right
        )
        self._draw_mouth(canvas, face, dy)

        return canvas.image

    @staticmethod
    def _draw_eye(canvas, cx, cy, openness):
        half_width = 4.0
        half_height = 6.5 * max(0.04, openness)

        if openness < 0.12:
            canvas.line(
                cx - half_width, cy, cx + half_width, cy,
                WHITE, width=2.0,
            )
            return

        canvas.rounded_rectangle(
            cx - half_width, cy - half_height,
            cx + half_width, cy + half_height,
            radius=2.8, fill=WHITE,
        )

    @staticmethod
    def _draw_mouth(canvas, face, dy):
        center_y = 24.2 + dy
        width = 4.0 + face.mouth_width * 8.0

        if face.mouth_open > 0.12:
            height = 2.0 + face.mouth_open * 4.0
            x0 = 16 - width / 2
            x1 = 16 + width / 2
            y0 = center_y - height / 2
            y1 = center_y + height / 2
            if face.mouth_curve >= 0:
                canvas.pieslice(x0, y0, x1, y1, 0, 180, WHITE)
            else:
                canvas.pieslice(x0, y0, x1, y1, 180, 360, WHITE)
            return

        points = []
        for index in range(9):
            t = index / 8.0
            x = 16 - width / 2 + width * t
            y = center_y + face.mouth_curve * 3.2 * math.sin(math.pi * t)
            points.append((x, y))
        canvas.polyline(points, WHITE, width=1.7)
