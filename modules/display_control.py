# modules/display_control.py
import subprocess
import psutil
from threading import Thread, Timer
import time
import os
import uuid
from PIL import Image
from .settings_handler import read_settings

_last_process_call_time = 0.0
_throttle_interval = 5  # Adjust as needed (seconds)
_pending_process_args = None
_throttle_timer = None
_current_image_name = None
_current_command_line = None
_current_static_folder = None
_current_rotation_offset = 0


def get_pixel_mapper_config(settings, rotation):
    """Determine the correct pixel-mapper configuration based on panel layout."""
    parallel = int(settings.get('parallelChains', 1))
    chain = int(settings.get('chainLength', 1))

    # U-mapper requires: parallel > 1 AND chain >= 4 AND chain is even
    if parallel > 1 and chain >= 4 and chain % 2 == 0:
        return f"U-mapper;Rotate:{rotation}"
    else:
        return f"Rotate:{rotation}"


def get_matrix_dimensions(settings):
    width = int(settings['widthInPixel']) * int(settings['chainLength'])
    height = int(settings['heightInPixel']) * int(settings['parallelChains'])
    return width, height


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


def process_image_for_display(image_path, settings):
    matrix_width, matrix_height = get_matrix_dimensions(settings)
    temp_path = None

    try:
        with Image.open(image_path) as img:
            if img.format == 'GIF' and getattr(img, 'n_frames', 1) > 1:
                frames = []
                durations = []

                for frame_idx in range(img.n_frames):
                    img.seek(frame_idx)
                    frame = img.convert('RGBA')
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


def _start_display_process(image_name, command_line, static_folder, rotation_offset=0):
    stopProcess()
    settings = read_settings()

    base_rotation = 270
    if settings["direction"] == "horizontal":
        base_rotation = 180
    elif settings["direction"] == "verticalTurned":
        base_rotation = 90
    elif settings["direction"] == "horizontalTurned":
        base_rotation = 0

    final_rotation = (base_rotation + rotation_offset) % 360
    pixel_mapper = get_pixel_mapper_config(settings, final_rotation)

    if static_folder != "static/giphy_cache" and static_folder != "static/immich_cache":
        static_folder = "static/pictures"

    command = ""
    processed_image_path = None
    original_path = None

    if command_line == "displayImage":
        original_path = f"{static_folder}/{image_name}"
        processed_image_path = process_image_for_display(original_path, settings)

        command = f"sudo .././rpi-rgb-led-matrix/utils/led-image-viewer -C --led-rows={settings['heightInPixel']} --led-cols={settings['widthInPixel']} --led-chain={settings['chainLength']} --led-parallel={settings['parallelChains']} --led-brightness={settings.get('displayBrightness', 100)} --led-pixel-mapper=\"{pixel_mapper}\" --led-slowdown-gpio={settings['ledSlowdown']} {processed_image_path} &"
    elif command_line == "displayDemo":
        if image_name == 12:
            command = f"sudo .././rpi-rgb-led-matrix/examples-api-use/clock -f ../rpi-rgb-led-matrix/fonts/4x6.bdf -d '%A' -d '%H:%M:%S' --led-rows={settings['heightInPixel']} --led-cols={settings['widthInPixel']} --led-chain={settings['chainLength']} --led-parallel={settings['parallelChains']} --led-brightness={settings.get('displayBrightness', 100)} --led-pixel-mapper=\"{pixel_mapper}\" --led-slowdown-gpio={settings['ledSlowdown']} &"
        elif image_name <= 11:
            command = f"sudo .././rpi-rgb-led-matrix/examples-api-use/demo -D{image_name} --led-rows={settings['heightInPixel']} --led-cols={settings['widthInPixel']} --led-chain={settings['chainLength']} --led-parallel={settings['parallelChains']} --led-brightness={settings.get('displayBrightness', 100)} --led-pixel-mapper=\"{pixel_mapper}\" --led-slowdown-gpio={settings['ledSlowdown']} &"

    if command:
        print(f"Executing command: {command}")
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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


def process_image_async(image_name, command_line, static_folder, angle_delta=None):
    global _last_process_call_time, _pending_process_args, _throttle_timer
    global _current_image_name, _current_command_line, _current_static_folder, _current_rotation_offset

    _current_image_name = image_name
    _current_command_line = command_line
    _current_static_folder = static_folder

    if angle_delta is None:
        _current_rotation_offset = 0
    else:
        _current_rotation_offset = (_current_rotation_offset + angle_delta) % 360

    current_time = time.time()
    time_since_last_call = current_time - _last_process_call_time

    if time_since_last_call >= _throttle_interval:
        _last_process_call_time = current_time
        _start_display_process(image_name, command_line, static_folder, _current_rotation_offset)
        if _throttle_timer and _throttle_timer.is_alive():
            _throttle_timer.cancel()
        _pending_process_args = None
    else:
        # A call happened recently, schedule a call if one isn't already pending
        _pending_process_args = (image_name, command_line, static_folder, _current_rotation_offset)
        if not _throttle_timer or not _throttle_timer.is_alive():
            _throttle_timer = Timer(_throttle_interval, _process_pending_call)
            _throttle_timer.start()
        else:
            print("Throttling: A pending process call is already scheduled.")


def _process_pending_call():
    global _pending_process_args, _last_process_call_time, _throttle_timer
    if _pending_process_args:
        image_name, command_line, static_folder, rotation_offset = _pending_process_args
        _last_process_call_time = time.time()
        _start_display_process(image_name, command_line, static_folder, rotation_offset)
        _pending_process_args = None
        _throttle_timer = None


def stopProcess():
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

def trigger_rotation(angle_delta):
    global _current_image_name, _current_command_line, _current_static_folder
    if _current_image_name:
        process_thread = Thread(target=process_image_async,
                                args=(_current_image_name, _current_command_line, _current_static_folder, angle_delta))
        process_thread.start()


is_not_running = True