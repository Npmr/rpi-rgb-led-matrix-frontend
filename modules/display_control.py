# modules/display_control.py
import subprocess
import psutil
from threading import Thread, Timer
import time
from .settings_handler import read_settings

_last_process_call_time = 0.0
_throttle_interval = 5  # Adjust as needed (seconds)
_pending_process_args = None
_throttle_timer = None

def _start_display_process(image_name, command_line, static_folder):
    stopProcess()
    settings = read_settings()
    rotation = ";Rotate:270"
    if settings["direction"] == "horizontal":
        rotation = ";Rotate:180"
    if settings["direction"] == "verticalTurned":
        rotation = ";Rotate:90"
    if settings["direction"] == "horizontalTurned":
        rotation = ";Rotate:0"

    if static_folder != "static/giphy_cache":
        static_folder = "static/pictures"

    command = ""
    if command_line == "displayImage":
        command = f"sudo .././rpi-rgb-led-matrix/utils/led-image-viewer -C --led-rows={settings['heightInPixel']} --led-cols={settings['widthInPixel']} --led-chain={settings['chainLength']} --led-parallel={settings['parallelChains']} --led-brightness=50 --led-pixel-mapper=\"U-mapper{rotation}\" --led-slowdown-gpio={settings['ledSlowdown']} {static_folder}/{image_name} &"
    elif command_line == "displayDemo":
        if image_name == 12:
            command = f"sudo .././rpi-rgb-led-matrix/examples-api-use/clock -f ../rpi-rgb-led-matrix/fonts/9x18B.bdf -d '%A' -d '%H:%M:%S' --led-rows={settings['heightInPixel']} --led-cols={settings['widthInPixel']} --led-chain={settings['chainLength']} --led-parallel={settings['parallelChains']} --led-brightness=50 --led-pixel-mapper=\"U-mapper{rotation}\" --led-slowdown-gpio={settings['ledSlowdown']} &"
        elif image_name <= 11:
            command = f"sudo .././rpi-rgb-led-matrix/examples-api-use/demo -D{image_name} --led-rows={settings['heightInPixel']} --led-cols={settings['widthInPixel']} --led-chain={settings['chainLength']} --led-parallel={settings['parallelChains']} --led-brightness=50 --led-pixel-mapper=\"U-mapper{rotation}\" --led-slowdown-gpio={settings['ledSlowdown']} &"

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

        output_thread = Thread(target=capture_output)
        output_thread.daemon = True
        output_thread.start()
    else:
        _is_process_running = False

def process_image_async(image_name, command_line, static_folder):
    global _last_process_call_time, _pending_process_args, _throttle_timer

    current_time = time.time()
    time_since_last_call = current_time - _last_process_call_time

    if time_since_last_call >= _throttle_interval:
        _last_process_call_time = current_time
        _start_display_process(image_name, command_line, static_folder)
        if _throttle_timer and _throttle_timer.is_alive():
            _throttle_timer.cancel()
        _pending_process_args = None
    else:
        # A call happened recently, schedule a call if one isn't already pending
        _pending_process_args = (image_name, command_line, static_folder)
        if not _throttle_timer or not _throttle_timer.is_alive():
            _throttle_timer = Timer(_throttle_interval, _process_pending_call) # Changed the delay here
            _throttle_timer.start()
        else:
            print("Throttling: A pending process call is already scheduled.")

def _process_pending_call():
    global _pending_process_args, _last_process_call_time, _throttle_timer
    if _pending_process_args:
        image_name, command_line, static_folder = _pending_process_args
        _last_process_call_time = time.time()
        _start_display_process(image_name, command_line, static_folder)
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

# Initialize the flag
is_not_running = True