# modules/display_control.py
import asyncio
import os
import subprocess
import time
from threading import Thread
from typing import Optional
from PIL import Image

from .settings_handler import read_settings


class DisplayController:
    def __init__(self):
        self._matrix = None
        self._options = None
        self._current_task = None
        self._stop_event = asyncio.Event()
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._worker_thread: Optional[Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._current_rotation = 0
        self._base_rotation = 270
        self._brightness = 100
        self._settings = None

    def _get_base_rotation(self, direction: str) -> int:
        rotations = {
            "horizontal": 180,
            "verticalTurned": 90,
            "horizontalTurned": 0,
            "vertical": 270,
        }
        return rotations.get(direction, 270)

    def _create_matrix_options(self, settings: dict, rotation: int):
        from rgbmatrix import RGBMatrixOptions

        options = RGBMatrixOptions()
        options.rows = int(settings["heightInPixel"])
        options.cols = int(settings["widthInPixel"])
        options.chain_length = int(settings["chainLength"])
        options.parallel = int(settings["parallelChains"])
        options.brightness = int(settings.get("displayBrightness", 100))
        options.gpio_slowdown = int(settings.get("ledSlowdown", 1))
        options.hardware_mapping = "regular"
        options.drop_privileges = False

        pixel_mapper = f"U-mapper;Rotate:{rotation}"
        options.pixel_mapper_config = pixel_mapper

        return options

    def _initialize_matrix(self, settings: dict):
        from rgbmatrix import RGBMatrix

        self._settings = settings
        self._base_rotation = self._get_base_rotation(settings.get("direction", "vertical"))
        rotation = (self._base_rotation + self._current_rotation) % 360
        self._options = self._create_matrix_options(settings, rotation)
        self._brightness = int(settings.get("displayBrightness", 100))

        if self._matrix:
            self._matrix.Clear()
            del self._matrix

        self._matrix = RGBMatrix(options=self._options)
        self._matrix.brightness = self._brightness

    def _ensure_matrix(self):
        if self._matrix is None:
            self._initialize_matrix(read_settings())

    def _process_image(self, image_path: str, settings: dict) -> Image.Image:
        matrix_width = int(settings["widthInPixel"]) * int(settings["chainLength"])
        matrix_height = int(settings["heightInPixel"]) * int(settings["parallelChains"])

        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (0, 0, 0))
                if img.mode == "P":
                    img = img.convert("RGBA")
                mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
                background.paste(img, mask=mask)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            img_ratio = img.width / img.height
            target_ratio = matrix_width / matrix_height

            if img_ratio > target_ratio:
                new_height = matrix_height
                new_width = int(matrix_height * img_ratio)
            else:
                new_width = matrix_width
                new_height = int(matrix_width / img_ratio)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            left = (img.width - matrix_width) // 2
            top = (img.height - matrix_height) // 2
            right = left + matrix_width
            bottom = top + matrix_height

            return img.crop((left, top, right, bottom))

    def _display_static_image(self, image_path: str):
        self._ensure_matrix()
        processed = self._process_image(image_path, self._settings)
        self._matrix.SetImage(processed.convert("RGB"))

    def _display_gif(self, image_path: str, duration: float = 0):
        self._ensure_matrix()
        matrix_width = self._matrix.width
        matrix_height = self._matrix.height

        with Image.open(image_path) as gif:
            n_frames = getattr(gif, "n_frames", 1)
            if n_frames <= 1:
                self._display_static_image(image_path)
                return

            frames = []
            durations = []

            for frame_idx in range(n_frames):
                gif.seek(frame_idx)
                frame = gif.convert("RGBA")

                img_ratio = frame.width / frame.height
                target_ratio = matrix_width / matrix_height

                if img_ratio > target_ratio:
                    new_height = matrix_height
                    new_width = int(matrix_height * img_ratio)
                else:
                    new_width = matrix_width
                    new_height = int(matrix_width / img_ratio)

                frame = frame.resize((new_width, new_height), Image.Resampling.LANCZOS)

                left = (frame.width - matrix_width) // 2
                top = (frame.height - matrix_height) // 2
                right = left + matrix_width
                bottom = top + matrix_height

                frame = frame.crop((left, top, right, bottom))

                canvas = self._matrix.CreateFrameCanvas()
                canvas.SetImage(frame.convert("RGB"))
                frames.append(canvas)
                durations.append(gif.info.get("duration", 100) / 1000.0)

        if duration <= 0:
            duration = sum(durations) * 3

        end_time = time.time() + duration
        frame_idx = 0

        while time.time() < end_time and not self._stop_event.is_set():
            canvas = frames[frame_idx]
            canvas = self._matrix.SwapOnVSync(canvas)
            time.sleep(durations[frame_idx])
            frame_idx = (frame_idx + 1) % len(frames)

        self._matrix.Clear()

    def _run_demo(self, demo_num: int):
        settings = self._settings or read_settings()
        rotation = (self._base_rotation + self._current_rotation) % 360
        pixel_mapper = f"U-mapper;Rotate:{rotation}"

        if demo_num == 12:
            cmd = [
                "sudo", ".././rpi-rgb-led-matrix/examples-api-use/clock",
                "-f", "../rpi-rgb-led-matrix/fonts/4x6.bdf",
                "-d", "%A", "-d", "%H:%M:%S",
                f"--led-rows={settings['heightInPixel']}",
                f"--led-cols={settings['widthInPixel']}",
                f"--led-chain={settings['chainLength']}",
                f"--led-parallel={settings['parallelChains']}",
                f"--led-brightness={settings.get('displayBrightness', 100)}",
                f"--led-pixel-mapper={pixel_mapper}",
                f"--led-slowdown-gpio={settings['ledSlowdown']}",
            ]
        else:
            cmd = [
                "sudo", ".././rpi-rgb-led-matrix/examples-api-use/demo",
                f"-D{demo_num}",
                f"--led-rows={settings['heightInPixel']}",
                f"--led-cols={settings['widthInPixel']}",
                f"--led-chain={settings['chainLength']}",
                f"--led-parallel={settings['parallelChains']}",
                f"--led-brightness={settings.get('displayBrightness', 100)}",
                f"--led-pixel-mapper={pixel_mapper}",
                f"--led-slowdown-gpio={settings['ledSlowdown']}",
            ]

        self._stop_current()
        self._stop_event.clear()
        process = subprocess.Popen(cmd)
        self._current_task = ("subprocess", process)

    def _stop_current(self):
        self._stop_event.set()
        if self._matrix:
            self._matrix.Clear()

        if self._current_task:
            task_type, task_obj = self._current_task
            if task_type == "subprocess" and task_obj.poll() is None:
                task_obj.terminate()
                try:
                    task_obj.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    task_obj.kill()
            self._current_task = None

    async def _worker(self):
        while True:
            cmd = await self._command_queue.get()
            if cmd is None:
                break

            action = cmd.get("action")
            try:
                if action == "display_image":
                    self._stop_current()
                    self._stop_event.clear()
                    self._display_static_image(cmd["path"])
                    self._current_task = ("static", cmd["path"])

                elif action == "display_gif":
                    self._stop_current()
                    self._stop_event.clear()
                    self._display_gif(cmd["path"], cmd.get("duration", 0))
                    self._current_task = ("gif", cmd["path"])

                elif action == "display_demo":
                    self._run_demo(cmd["demo_num"])

                elif action == "stop":
                    self._stop_current()

                elif action == "set_brightness":
                    if self._matrix:
                        self._matrix.brightness = cmd["value"]
                    self._brightness = cmd["value"]

                elif action == "rotate":
                    self._current_rotation = (self._current_rotation + cmd["delta"]) % 360
                    self._initialize_matrix(self._settings or read_settings())

                    if self._current_task and self._current_task[0] in ("static", "gif"):
                        path = self._current_task[1]
                        if path.lower().endswith(".gif"):
                            self._display_gif(path)
                        else:
                            self._display_static_image(path)

            except Exception as e:
                print(f"Display error: {e}")
            finally:
                self._command_queue.task_done()

    def start(self):
        if self._worker_thread is None or not self._worker_thread.is_alive():
            def run_loop():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                self._loop.run_until_complete(self._worker())

            self._worker_thread = Thread(target=run_loop, daemon=True)
            self._worker_thread.start()
            time.sleep(0.1)

    def stop(self):
        self._stop_current()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._command_queue.put_nowait, None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)
        if self._matrix:
            self._matrix.Clear()
            del self._matrix
            self._matrix = None

    def display_image(self, image_name: str, static_folder: str):
        path = os.path.join(static_folder, image_name)
        if not os.path.exists(path):
            print(f"Image not found: {path}")
            return
        self._enqueue({"action": "display_image", "path": path})

    def display_gif(self, image_name: str, static_folder: str, duration: float = 0):
        path = os.path.join(static_folder, image_name)
        if not os.path.exists(path):
            print(f"GIF not found: {path}")
            return
        self._enqueue({"action": "display_gif", "path": path, "duration": duration})

    def display_demo(self, demo_num: int):
        self._enqueue({"action": "display_demo", "demo_num": demo_num})

    def stop(self):
        self._enqueue({"action": "stop"})

    def set_brightness(self, value: int):
        self._brightness = max(1, min(100, value))
        self._enqueue({"action": "set_brightness", "value": self._brightness})

    def rotate(self, angle_delta: int):
        self._current_rotation = (self._current_rotation + angle_delta) % 360
        self._enqueue({"action": "rotate", "delta": angle_delta})

    def _enqueue(self, cmd: dict):
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._command_queue.put_nowait, cmd)

    def update_settings(self, settings: dict):
        self._settings = settings
        self._base_rotation = self._get_base_rotation(settings.get("direction", "vertical"))
        self._initialize_matrix(settings)


_display_controller: Optional[DisplayController] = None


def get_display_controller() -> DisplayController:
    global _display_controller
    if _display_controller is None:
        _display_controller = DisplayController()
        _display_controller.start()
    return _display_controller


def process_image_async(image_name: str, command_line: str, static_folder: str, angle_delta: Optional[int] = None):
    controller = get_display_controller()

    if angle_delta is not None:
        controller.rotate(angle_delta)
        return

    if command_line == "displayImage":
        controller.display_image(image_name, static_folder)
    elif command_line == "displayDemo":
        controller.display_demo(int(image_name))


def stopProcess():
    controller = get_display_controller()
    controller.stop()


def trigger_rotation(angle_delta: int):
    controller = get_display_controller()
    controller.rotate(angle_delta)


def set_brightness(value: int):
    controller = get_display_controller()
    controller.set_brightness(value)


def update_display_settings(settings: dict):
    controller = get_display_controller()
    controller.update_settings(settings)


is_not_running = True
