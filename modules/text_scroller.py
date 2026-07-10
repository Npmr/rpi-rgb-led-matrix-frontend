# modules/text_scroller.py
import time
import threading
from typing import Optional
from rgbmatrix import graphics


class TextScroller:
    def __init__(self, matrix):
        self._matrix = matrix
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_text = ""
        self._font = None
        self._font_path = ""
        self._text_color = graphics.Color(255, 255, 255)
        self._bg_color = graphics.Color(0, 0, 0)
        self._y_pos = 10
        self._speed = 0.05
        self._loop = True
        self._blink_on_for = 0
        self._blink_off_for = 0

    def load_font(self, font_path: str):
        font = graphics.Font()
        font.LoadFont(font_path)
        self._font = font
        self._font_path = font_path

    def set_text(self, text: str):
        self._current_text = text

    def set_colors(self, text_color: tuple, bg_color: tuple):
        self._text_color = graphics.Color(*text_color)
        self._bg_color = graphics.Color(*bg_color)

    def set_speed(self, speed: float):
        self._speed = max(0.01, speed)

    def set_y_pos(self, y: int):
        self._y_pos = y

    def set_loop(self, loop: bool):
        self._loop = loop

    def set_blink(self, on_pixels: int, off_pixels: int):
        self._blink_on_for = on_pixels
        self._blink_off_for = off_pixels

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not self._font:
            self.load_font("../rpi-rgb-led-matrix/fonts/7x13.bdf")
        if not self._current_text:
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        if not self._font or not self._current_text:
            return

        main_canvas = self._matrix.CreateFrameCanvas()
        bg_canvas = self._matrix.CreateFrameCanvas()
        bg_canvas.Fill(self._bg_color.red, self._bg_color.green, self._bg_color.blue)

        x_pos = main_canvas.width
        text_width = graphics.DrawText(main_canvas, self._font, 0, 0, self._text_color, self._current_text)

        loop_count = 0
        max_loops = float("inf") if self._loop else 1

        blink_on_for = self._blink_on_for
        blink_off_for = self._blink_off_for
        blink_on = True
        blink_ct = 0

        while not self._stop_event.is_set() and loop_count < max_loops:
            x_pos -= 1

            if blink_on_for > 0 and blink_off_for > 0:
                if blink_on:
                    if blink_ct >= blink_on_for:
                        blink_on = False
                        blink_ct = 0
                    main_canvas.Fill(self._bg_color.red, self._bg_color.green, self._bg_color.blue)
                    graphics.DrawText(main_canvas, self._font, x_pos, self._y_pos, self._text_color, self._current_text)
                    main_canvas = self._matrix.SwapOnVSync(main_canvas)
                    if x_pos + text_width < 0:
                        loop_count += 1
                        x_pos = main_canvas.width
                else:
                    if blink_ct >= blink_off_for:
                        blink_on = True
                        blink_ct = 0
                    self._matrix.SwapOnVSync(bg_canvas)
                blink_ct += 1
            else:
                main_canvas.Fill(self._bg_color.red, self._bg_color.green, self._bg_color.blue)
                graphics.DrawText(main_canvas, self._font, x_pos, self._y_pos, self._text_color, self._current_text)
                main_canvas = self._matrix.SwapOnVSync(main_canvas)
                if x_pos + text_width < 0:
                    loop_count += 1
                    x_pos = main_canvas.width

            time.sleep(self._speed)

        self._matrix.Clear()
