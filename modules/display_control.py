# modules/display_control.py
import subprocess
import sys
import psutil
from threading import Thread, Timer
import time
import os
import re
import uuid
from PIL import Image
from .settings_handler import choice_setting, read_settings
from .geometry import (
    get_base_rotation,
    get_display_geometry,
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


IMAGE_FIT_MODES = ("cover", "contain", "stretch")
IMAGE_FIT_ANCHORS = ("center", "top", "bottom", "left", "right")


def get_image_fit_mode(settings):
    """Scaling mode for full screen pictures: cover, contain or stretch."""
    return choice_setting(settings, "imageFitMode", IMAGE_FIT_MODES, "cover")


def get_image_fit_anchor(settings):
    """Which edge keeps visible when a picture has to be cropped/positioned."""
    return choice_setting(settings, "imageFitAnchor", IMAGE_FIT_ANCHORS, "center")


def _background_color(mode, background):
    """Return a fill colour that is valid for the given image mode."""
    if mode in ("RGBA", "LA"):
        if len(background) == 4:
            return tuple(int(c) for c in background)
        return tuple(int(c) for c in background) + (255,)
    return tuple(int(c) for c in background)


def fit_image(img, target_width, target_height, mode="cover", anchor="center",
              background=(0, 0, 0)):
    """Scale ``img`` onto a ``target_width`` x ``target_height`` canvas.

    ``mode``:
        cover   - scale up until the canvas is fully covered, crop the overflow
        contain - scale down until the whole image fits, letterbox the rest
        stretch - scale exactly to the canvas, ignoring the aspect ratio
    ``anchor`` decides which edge/content stays visible when there is a choice
    (crop side for cover, alignment for contain).
    """
    target_width = max(1, int(target_width))
    target_height = max(1, int(target_height))
    if img.width <= 0 or img.height <= 0:
        return img

    if mode == "stretch":
        return img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    if mode == "contain":
        ratio = min(target_width / img.width, target_height / img.height)
        new_size = (max(1, round(img.width * ratio)), max(1, round(img.height * ratio)))
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        canvas = Image.new(
            img.mode,
            (target_width, target_height),
            _background_color(img.mode, background),
        )
        x = (target_width - resized.width) // 2
        y = (target_height - resized.height) // 2
        if anchor == "top":
            y = 0
        elif anchor == "bottom":
            y = target_height - resized.height
        elif anchor == "left":
            x = 0
        elif anchor == "right":
            x = target_width - resized.width
        canvas.paste(resized, (x, y))
        return canvas

    # cover
    ratio = max(target_width / img.width, target_height / img.height)
    new_size = (max(1, round(img.width * ratio)), max(1, round(img.height * ratio)))
    resized = img.resize(new_size, Image.Resampling.LANCZOS)

    left = (resized.width - target_width) // 2
    top = (resized.height - target_height) // 2
    if anchor == "top":
        top = 0
    elif anchor == "bottom":
        top = max(0, resized.height - target_height)
    elif anchor == "left":
        left = 0
    elif anchor == "right":
        left = max(0, resized.width - target_width)

    return resized.crop((left, top, left + target_width, top + target_height))


def fill_crop_image(img, target_width, target_height):
    """Backwards compatible wrapper: fill the canvas and crop the overflow."""
    return fit_image(img, target_width, target_height, "cover", "center")


def process_image_for_display(image_path, settings, exif_orientation=None,
                              width=None, height=None):
    """Crop and resize ``image_path`` to the canvas the driver exposes.

    The target size must be the *visible* canvas (after pixel mappers), not the
    raw matrix: with a folding U-mapper a raw 384x64 matrix becomes a 192x128
    canvas, and ``led-image-viewer`` would otherwise letterbox the image into a
    thin strip because it fits images into the canvas size preserving the
    aspect ratio.

    ``width``/``height`` may be passed in when the caller already knows the
    final geometry (for example when the rotate feature adds an offset).
    """
    if width is None or height is None:
        geometry = get_display_geometry(settings)
        width, height = geometry["width"], geometry["height"]
    fit_mode = get_image_fit_mode(settings)
    fit_anchor = get_image_fit_anchor(settings)
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
                    processed_frame = fit_image(
                        frame, width, height, fit_mode, fit_anchor)
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

                processed_img = fit_image(
                    img, width, height, fit_mode, fit_anchor)

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


def _parse_reported_size(output):
    """Extract the canvas size a rpi-rgb-led-matrix tool reports on startup.

    The tools print ``Size: 192x128. Hardware gpio mapping: ...``. Comparing
    that with the derived geometry catches wiring/mapper mismatches early.
    """
    if not output:
        return None
    match = re.search(r"Size:\s*(\d+)\s*x\s*(\d+)", output)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _base_matrix_dir():
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'rpi-rgb-led-matrix')
    )


def _viewer_command(image_path, settings, geometry):
    """Build the ``led-image-viewer`` command for an already prepared image."""
    base_matrix_dir = _base_matrix_dir()
    rows = _get_int_setting(settings, 'heightInPixel', 32)
    cols = _get_int_setting(settings, 'widthInPixel', 32)
    chain = _get_int_setting(settings, 'chainLength', 1)
    parallel = _get_int_setting(settings, 'parallelChains', 1)
    brightness = _get_int_setting(settings, 'displayBrightness', 100)
    slowdown = _get_int_setting(settings, 'ledSlowdown', 2)

    return [
        "sudo",
        os.path.join(base_matrix_dir, "utils", "led-image-viewer"),
        "-C",
        f"--led-rows={rows}",
        f"--led-cols={cols}",
        f"--led-chain={chain}",
        f"--led-parallel={parallel}",
        f"--led-brightness={brightness}",
        f"--led-pixel-mapper={geometry['pixelMapper']}",
        f"--led-slowdown-gpio={slowdown}",
        image_path,
    ]


def _launch_display_command(cmd, geometry=None, env=None, cleanup_path=None):
    """Start a display command and remove ``cleanup_path`` once it exits."""
    global _is_process_running
    print(f"Executing: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _is_process_running = True

    def capture_output():
        stdout, stderr = process.communicate()
        if stdout:
            text = stdout.decode(errors="replace")
            print(f"Process output: {text}")
            if geometry is not None:
                reported = _parse_reported_size(text)
                expected = (geometry["width"], geometry["height"])
                if reported and reported != expected:
                    print(
                        f"Warning: driver reports a {reported[0]}x{reported[1]} canvas "
                        f"but settings imply {expected[0]}x{expected[1]}. "
                        "Check the panel wiring (chainLength/parallelChains) and pixel mapper."
                    )
        if stderr:
            print(f"Process error: {stderr.decode(errors='replace')}")
        global _is_process_running
        _is_process_running = False
        if cleanup_path and os.path.exists(cleanup_path):
            try:
                os.remove(cleanup_path)
            except Exception as e:
                print(f"Error cleaning up temp file {cleanup_path}: {e}")

    output_thread = Thread(target=capture_output)
    output_thread.daemon = True
    output_thread.start()
    return process


def display_image_file(image_path, rotation_offset=0, cleanup_path=None):
    """Display an already prepared image/GIF file.

    Used by the startup screen, which renders its own content. ``cleanup_path``
    is deleted again once the viewer exits.
    """
    stopProcess()
    settings = read_settings()
    final_rotation = (get_base_rotation(settings) + rotation_offset) % 360
    geometry = get_display_geometry(settings, rotation=final_rotation)
    cmd = _viewer_command(image_path, settings, geometry)
    return _launch_display_command(cmd, geometry=geometry, cleanup_path=cleanup_path)


def _loop_is_running(keep_loops):
    """True while the slideshow that owns a picture is still running."""
    if 'giphy' in keep_loops:
        from . import giphy_controller
        return giphy_controller.giphy_running
    if 'immich' in keep_loops:
        return immich_controller.immich_running
    return True


def _start_display_process(image_name, command_line, static_folder, rotation_offset=0, exif_orientation=None):
    # Work out which playback loop this picture belongs to *before* the folder
    # name is normalised, so that loop can be kept alive while it shows its own
    # picture and every other loop is stopped.
    keep_loops = ()
    if static_folder == "static/giphy_cache":
        keep_loops = ('giphy',)
    elif static_folder == "static/immich_cache":
        keep_loops = ('immich',)

    # The slideshow may have been stopped while the picture was downloaded or
    # while a throttled display was queued. Showing it now would look like the
    # display restarted itself right after the Stop button was pressed.
    if keep_loops and not _loop_is_running(keep_loops):
        print("Not displaying the slideshow picture: the loop was stopped.")
        return

    stopProcess(keep_loops=keep_loops)
    settings = read_settings()

    base_rotation = get_base_rotation(settings)
    final_rotation = (base_rotation + rotation_offset) % 360
    geometry = get_display_geometry(settings, rotation=final_rotation)
    pixel_mapper = geometry["pixelMapper"]

    if static_folder not in ("static/giphy_cache", "static/immich_cache"):
        static_folder = "static/pictures"

    # Validate and sanitize all numeric settings before they reach subprocess args.
    rows = _get_int_setting(settings, 'heightInPixel', 32)
    cols = _get_int_setting(settings, 'widthInPixel', 32)
    chain = _get_int_setting(settings, 'chainLength', 1)
    parallel = _get_int_setting(settings, 'parallelChains', 1)
    brightness = _get_int_setting(settings, 'displayBrightness', 100)
    slowdown = _get_int_setting(settings, 'ledSlowdown', 2)

    base_matrix_dir = _base_matrix_dir()

    cmd = []
    cleanup_path = None
    original_path = None
    env = None

    if command_line == "displayImage":
        if not _is_safe_basename(image_name):
            print(f"Refusing to display image with unsafe name: {image_name!r}")
            _is_process_running = False
            return
        original_path = os.path.join(static_folder, image_name)
        processed_image_path = process_image_for_display(
            original_path,
            settings,
            exif_orientation,
            width=geometry["width"],
            height=geometry["height"],
        )
        if processed_image_path and processed_image_path != original_path:
            cleanup_path = processed_image_path
        cmd = _viewer_command(processed_image_path, settings, geometry)
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
        _launch_display_command(cmd, geometry=geometry, env=env,
                                cleanup_path=cleanup_path)
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


def _cancel_pending_display():
    """Drop a display call that is waiting for the throttle timer.

    Without this a queued picture would still appear a few seconds after the
    user pressed Stop, which looks like the display simply ignored the button.
    The throttle timestamp is left alone on purpose: resetting it would allow
    an immediate display again and defeat the throttle.
    """
    global _pending_process_args, _throttle_timer
    timer = _throttle_timer
    _throttle_timer = None
    _pending_process_args = None
    if timer is not None and timer.is_alive():
        timer.cancel()


def stopProcess(keep_loops=()):
    """Stop the current display and the loops that feed it.

    ``keep_loops`` names playback loops that must survive, because a loop that
    is displaying its own picture would otherwise stop itself: the Giphy and
    Immich loops call into the display path for every picture they show.
    """
    stop_grid_display()
    _cancel_pending_display()

    for process in psutil.process_iter():
        if "led-image-viewer" in process.name():
            process.kill()
            break
        if "demo" in process.name():
            process.kill()
            break
        settings = read_settings()
        if settings.get("displayTimeAndDate", "") == "":
            if "clock" in process.name():
                process.kill()
                break

    # Also stop the slideshow loops unless the caller is one of them.
    if 'immich' not in keep_loops:
        immich_controller.stop_immich_loop()
    if 'giphy' not in keep_loops:
        try:
            from . import giphy_controller
            giphy_controller.stop_giphy_loop()
        except Exception as error:  # pragma: no cover - defensive
            print(f"Could not stop the Giphy loop: {error}")

    # Any display action dismisses a startup screen that is still showing.
    try:
        from . import startup_screen
        startup_screen.cancel_startup_screen()
    except Exception:
        pass

def trigger_rotation(angle_delta):
    global _current_image_name, _current_command_line, _current_static_folder, _current_exif_orientation
    if _current_image_name:
        process_thread = Thread(target=process_image_async,
                                args=(_current_image_name, _current_command_line, _current_static_folder, angle_delta, _current_exif_orientation))
        process_thread.start()


