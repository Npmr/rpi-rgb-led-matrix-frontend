# modules/display_control.py
import subprocess
import psutil
from threading import Thread
from .settings_handler import read_settings # Import from the same module directory

def process_image_async(image_name, command_line, static_folder='static/pictures'):
    stopProcess()
    settings = read_settings()
    rotation = ";Rotate:270"
    if settings["direction"] == "horizontal":
        rotation = ";Rotate:180"
    if settings["direction"] == "verticalTurned":
        rotation = ";Rotate:90"
    if settings["direction"] == "horizontalTurned":
        rotation = ";Rotate:0"

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

        output_thread = Thread(target=capture_output)
        output_thread.start()

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