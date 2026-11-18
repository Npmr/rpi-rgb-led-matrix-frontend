# modules/bot/styles/robot.py
"""Cute robot face: rounded head, antenna, screen eyes and an LED mouth."""
import math

from .base import StyleCanvas, blend, parse_color

DEFAULT_COLOR = (0, 212, 255)
DEFAULT_ACCENT = (255, 176, 0)


class RobotStyle:
    id = "robot"
    label = "Cute robot"

    def render(self, width, height, face, options=None, background=None):
        options = options or {}
        color = parse_color(options.get("color"), DEFAULT_COLOR)
        accent = parse_color(options.get("accent"), DEFAULT_ACCENT)

        body = blend(color, (0, 0, 0), 0.82)
        ear = blend(color, (0, 0, 0), 0.38)
        pupil = blend(body, (0, 0, 0), 0.55)
        cheek = blend(accent, (255, 70, 70), 0.45)

        canvas = StyleCanvas(width, height, background=background)
        dy = face.bob * 1.5

        # Antenna and its little glowing ball.
        canvas.line(16, 2.5 + dy, 16, 7 + dy, accent, width=1.2)
        canvas.circle(16, 2.2 + dy, 2.6, blend(accent, body, 0.65))
        canvas.circle(16, 2.2 + dy, 1.9, accent)

        # Ears peek out from behind the head.
        canvas.rounded_rectangle(1, 13 + dy, 4, 21 + dy, 1, fill=ear)
        canvas.rounded_rectangle(28, 13 + dy, 31, 21 + dy, 1, fill=ear)

        # Head plate.
        canvas.rounded_rectangle(
            3, 7 + dy, 29, 27 + dy, 6,
            fill=body, outline=color, width=2,
        )

        self._draw_brows(canvas, face, accent, dy)
        self._draw_eye(canvas, 10.5, 16.5 + dy, face.eye_left, face, color, pupil)
        self._draw_eye(canvas, 21.5, 16.5 + dy, face.eye_right, face, color, pupil)
        self._draw_mouth(canvas, face, accent, dy)
        self._draw_cheeks(canvas, face, cheek, dy)

        return canvas.image

    @staticmethod
    def _draw_eye(canvas, cx, cy, openness, face, color, pupil):
        half_width = 2.7
        half_height = 3.6 * max(0.05, openness)

        if openness < 0.12:
            canvas.line(
                cx - half_width, cy, cx + half_width, cy,
                color, width=1.8,
            )
            return

        canvas.rounded_rectangle(
            cx - half_width, cy - half_height,
            cx + half_width, cy + half_height,
            1.4, fill=color,
        )
        if openness > 0.45:
            canvas.circle(
                cx + face.gaze_x * 1.2,
                cy + face.gaze_y * 1.0,
                1.2, pupil,
            )

    @staticmethod
    def _draw_brows(canvas, face, accent, dy):
        if abs(face.brow_tilt) < 0.05 and abs(face.brow_raise) < 0.05:
            return

        base = 11.2 + dy - face.brow_raise * 1.7
        inner = base - face.brow_tilt * 1.1
        outer = base + face.brow_tilt * 0.35
        canvas.line(7.0, outer, 12.5, inner, accent, width=1.1)
        canvas.line(25.0, outer, 19.5, inner, accent, width=1.1)

    @staticmethod
    def _draw_mouth(canvas, face, accent, dy):
        center_y = 22.4 + dy
        width = 4.0 + face.mouth_width * 8.0

        if face.mouth_open > 0.12:
            height = 2.2 + face.mouth_open * 4.6
            x0 = 16 - width / 2
            x1 = 16 + width / 2
            y0 = center_y - height / 2
            y1 = center_y + height / 2
            if face.mouth_curve >= 0:
                canvas.pieslice(x0, y0, x1, y1, 0, 180, accent)
            else:
                canvas.pieslice(x0, y0, x1, y1, 180, 360, accent)
            return

        points = []
        for index in range(9):
            t = index / 8.0
            x = 16 - width / 2 + width * t
            y = center_y + face.mouth_curve * 3.2 * math.sin(math.pi * t)
            points.append((x, y))
        canvas.polyline(points, accent, width=1.5)

    @staticmethod
    def _draw_cheeks(canvas, face, cheek, dy):
        if face.blush < 0.1:
            return
        radius = 0.5 + face.blush * 1.1
        canvas.ellipse(7.6, 20.4 + dy, radius, radius * 0.7, cheek)
        canvas.ellipse(24.4, 20.4 + dy, radius, radius * 0.7, cheek)
