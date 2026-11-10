# modules/display_control.py
import subprocess
import sys
import psutil
from threading import Thread, Timer
import time
import os
import uuid
from PIL import Image
from .settings_handler import read_settings
from .geometry import (
    get_base_rotation,
    get_matrix_dimensions,
    get_pixel_mapper_config,
)

from . import immich_controller
_last_process_call_time = 0.0
_throttle_interval = 5  # Adjust as needed (seconds)
_pending_process_args = None
_throttle_timer = None
_current_image_name = None
_current_command_line = None
_current_static_folder = None
_current_rotation_offset = 0
_current_exif_orientation = None
_is_process_running = False
_grid_process = None


def apply_exif_orientation(img, orientation):
    """Apply EXIF orientation correction to PIL Image.
    
    EXIF Orientation values (1-8):
    1 = Normal (no rotation)
    2 = Flip horizontal
    3 = Rotate 180
    4 = Flip vertical
    5 = Transpose (flip horizontal + rotate 90 CW)
    6 = Rotate 90 CW
    7 = Transverse (flip horizontal + rotate 90 CCW)
    8 = Rotate 90 CCW
    """
    if not orientation or orientation == 1:
        return img
    
    try:
        orientation = int(orientation)
    except (ValueError, TypeError):
        return img
    
    if orientation == 2:
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif orientation == 3:
        return img.transpose(Image.Transpose.ROTATE_180)
    elif orientation == 4:
        return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    elif orientation == 5:
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(Image.Transpose.ROTATE_90)
    elif orientation == 6:
        return img.transpose(Image.Transpose.ROTATE_270)  # 90 CW
    elif orientation == 7:
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(Image.Transpose.ROTATE_270)
    elif orientation == 8:
        return img.transpose(Image.Transpose.ROTATE_90)   # 90 CCW
    
    return img


def fill_crop_image(img, target_width, target_height):
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height

    if img_ratio > target_ratio:
        new_height = target_height
        new_width = int(target_height * img_ratio)
    else:
        new_width = target_width
        new_height = int(target_width / img_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    left = (img.width - target_width) // 2
    top = (img.height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    return img.crop((left, top, right, bottom))


def process_image_for_display(image_path, settings, exif_orientation=None):
    matrix_width, matrix_height = get_matrix_dimensions(settings)
    temp_path = None

    try:
        with Image.open(image_path) as img:
            # Apply EXIF orientation correction if enabled and available
            auto_orient = settings.get('immichAutoOrientation', 'true') == 'true'
            if auto_orient and exif_orientation:
                img = apply_exif_orientation(img, exif_orientation)

            if img.format == 'GIF' and getattr(img, 'n_frames', 1) > 1:
                frames = []
                durations = []

                for frame_idx in range(img.n_frames):
                    img.seek(frame_idx)
                    frame = img.convert('RGBA')
                    # Apply EXIF orientation to each frame
                    if auto_orient and exif_orientation:
                        frame = apply_exif_orientation(frame, exif_orientation)
                    processed_frame = fill_crop_image(frame, matrix_width, matrix_height)
                    frames.append(processed_frame)
                    durations.append(img.info.get('duration', 100))

                temp_path = f"/tmp/led_display_{uuid.uuid4().hex}.gif"
                frames[0].save(
                    temp_path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=0,
                    optimize=False,
                    colors=256
                )
            else:
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (0, 0, 0))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                processed_img = fill_crop_image(img, matrix_width, matrix_height)

                ext = os.path.splitext(image_path)[1].lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                    ext = '.png'
                temp_path = f"/tmp/led_display_{uuid.uuid4().hex}{ext}"
                processed_img.save(temp_path)

        return temp_path
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        return image_path


def _get_int_setting(settings, key, default):
    """Safely parse an integer setting, returning the default on any failure.

    This prevents non-numeric (or malicious) settings values from being
    interpolated into subprocess arguments.
    """
    try:
        return int(settings.get(key, default))
    except (ValueError, TypeError):
        return default


def _is_safe_basename(filename):
    """Return True only if filename is a plain basename (no traversal/separators)."""
    if not filename:
        return False
    if '/' in filename or '\\' in filename or '..' in filename:
        return False
    return os.path.basename(filename) == filename


def _start_display_process(image_name, command_line, static_folder, rotation_offset=0, exif_orientation=None):
    stopProcess()
    settings = read_settings()

    base_rotation = get_base_rotation(settings)
    final_rotation = (base_rotation + rotation_offset) % 360
    pixel_mapper = get_pixel_mapper_config(settings, final_rotation)

    if static_folder not in ("static/giphy_cache", "static/immich_cache"):
        static_folder = "static/pictures"

    # Validate and sanitize all numeric settings before they reach subprocess args.
    rows = _get_int_setting(settings, 'heightInPixel', 32)
    cols = _get_int_setting(settings, 'widthInPixel', 32)
    chain = _get_int_setting(settings, 'chainLength', 1)
    parallel = _get_int_setting(settings, 'parallelChains', 1)
    brightness = _get_int_setting(settings.get('displayBrightness', 100), 100)
    slowdown = _get_int_setting(settings.get('ledSlowdown', 2), 2)

    base_matrix_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'rpi-rgb-led-matrix')
    )

    cmd = []
    processed_image_path = None
    original_path = None
    env = None

    if command_line == "displayImage":
        if not _is_safe_basename(image_name):
            print(f"Refusing to display image with unsafe name: {image_name!r}")
            _is_process_running = False
            return
        original_path = os.path.join(static_folder, image_name)
        processed_image_path = process_image_for_display(original_path, settings, exif_orientation)

        cmd = [
            "sudo",
            os.path.join(base_matrix_dir, "utils", "led-image-viewer"),
            "-C",
            f"--led-rows={rows}",
            f"--led-cols={cols}",
            f"--led-chain={chain}",
            f"--led-parallel={parallel}",
            f"--led-brightness={brightness}",
            f"--led-pixel-mapper={pixel_mapper}",
            f"--led-slowdown-gpio={slowdown}",
            processed_image_path,
        ]
    elif command_line == "displayDemo":
        if image_name == 12:
            tz = settings.get('timezone', 'UTC')
            date_fmt = settings.get('clockFormatDate', '%A')
            time_fmt = settings.get('clockFormatTime', '%H:%M:%S')
            env = os.environ.copy()
            env["TZ"] = tz
            cmd = [
                "sudo",
                os.path.join(base_matrix_dir, "examples-api-use", "clock"),
                "-f", os.path.join(base_matrix_dir, "fonts", "4x6.bdf"),
                "-d", date_fmt,
                "-d", time_fmt,
                f"--led-rows={rows}",
                f"--led-cols={cols}",
                f"--led-chain={chain}",
                f"--led-parallel={parallel}",
                f"--led-brightness={brightness}",
                f"--led-pixel-mapper={pixel_mapper}",
                f"--led-slowdown-gpio={slowdown}",
            ]
        elif isinstance(image_name, int) and 1 <= image_name <= 11:
            cmd = [
                "sudo",
                os.path.join(base_matrix_dir, "examples-api-use", "demo"),
                f"-D{image_name}",
                f"--led-rows={rows}",
                f"--led-cols={cols}",
                f"--led-chain={chain}",
                f"--led-parallel={parallel}",
                f"--led-brightness={brightness}",
                f"--led-pixel-mapper={pixel_mapper}",
                f"--led-slowdown-gpio={slowdown}",
            ]

    if cmd:
        print(f"Executing: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def capture_output():
            stdout, stderr = process.communicate()
            if stdout:
                print(f"Process output: {stdout.decode()}")
            if stderr:
                print(f"Process error: {stderr.decode()}")
            global _is_process_running
            _is_process_running = False
            if processed_image_path and processed_image_path != original_path and os.path.exists(processed_image_path):
                try:
                    os.remove(processed_image_path)
                except Exception as e:
                    print(f"Error cleaning up temp file {processed_image_path}: {e}")

        output_thread = Thread(target=capture_output)
        output_thread.daemon = True
        output_thread.start()
    else:
        _is_process_running = False


def process_image_async(image_name, command_line, static_folder, angle_delta=None, exif_orientation=None):
    global _last_process_call_time, _pending_process_args, _throttle_timer
    global _current_image_name, _current_command_line, _current_static_folder, _current_rotation_offset, _current_exif_orientation

    _current_image_name = image_name
    _current_command_line = command_line
    _current_static_folder = static_folder
    _current_exif_orientation = exif_orientation

    if angle_delta is None:
        _current_rotation_offset = 0
    else:
        _current_rotation_offset = (_current_rotation_offset + angle_delta) % 360

    current_time = time.time()
    time_since_last_call = current_time - _last_process_call_time

    if time_since_last_call >= _throttle_interval:
        _last_process_call_time = current_time
        _start_display_process(image_name, command_line, static_folder, _current_rotation_offset, _current_exif_orientation)
        if _throttle_timer and _throttle_timer.is_alive():
            _throttle_timer.cancel()
        _pending_process_args = None
    else:
        # A call happened recently, schedule a call if one isn't already pending
        _pending_process_args = (image_name, command_line, static_folder, _current_rotation_offset, _current_exif_orientation)
        if not _throttle_timer or not _throttle_timer.is_alive():
            _throttle_timer = Timer(_throttle_interval, _process_pending_call)
            _throttle_timer.start()
        else:
            print("Throttling: A pending process call is already scheduled.")


def _process_pending_call():
    global _pending_process_args, _last_process_call_time, _throttle_timer
    if _pending_process_args:
        image_name, command_line, static_folder, rotation_offset, exif_orientation = _pending_process_args
        _last_process_call_time = time.time()
        _start_display_process(image_name, command_line, static_folder, rotation_offset, exif_orientation)
        _pending_process_args = None
        _throttle_timer = None


def stop_grid_display():
    """Stop the grid renderer process (including orphans after a restart)."""
    global _grid_process
    process = _grid_process
    _grid_process = None
    if process is not None and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        except Exception as error:  # pragma: no cover - defensive
            print(f"Error stopping grid display: {error}")

    # Fallback: kill any renderer that survived an application restart.
    for candidate in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = candidate.info.get('cmdline') or []
            if any('grid_display.py' in str(part) for part in cmdline):
                candidate.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def is_grid_running():
    if _grid_process is not None and _grid_process.poll() is None:
        return True
    for candidate in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = candidate.info.get('cmdline') or []
            if any('grid_display.py' in str(part) for part in cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def start_grid_display():
    """Start the grid renderer as a separate process (owns the matrix)."""
    global _grid_process
    stopProcess()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    script = os.path.join(project_root, 'grid_display.py')
    if not os.path.exists(script):
        print(f"Grid display script not found: {script}")
        return False

    if os.geteuid() == 0:
        cmd = [sys.executable, script]
    else:
        cmd = ["sudo", sys.executable, script]

    print(f"Starting grid display: {' '.join(cmd)}")
    try:
        _grid_process = subprocess.Popen(cmd, cwd=project_root)
    except Exception as error:
        print(f"Failed to start grid display: {error}")
        _grid_process = None
        return False
    return True


def stopProcess():
    stop_grid_display()

    for process in psutil.process_iter():
        if "led-image-viewer" in process.name():
            process.kill()
            break
        if "demo" in process.name():
            process.kill()
            break
        settings = read_settings()
        if settings["displayTimeAndDate"] == "":
            if "clock" in process.name():
                process.kill()
                break

    # Also stop Immich loop if running
    immich_controller.stop_immich_loop()

def trigger_rotation(angle_delta):
    global _current_image_name, _current_command_line, _current_static_folder, _current_exif_orientation
    if _current_image_name:
        process_thread = Thread(target=process_image_async,
                                args=(_current_image_name, _current_command_line, _current_static_folder, angle_delta, _current_exif_orientation))
        process_thread.start()


