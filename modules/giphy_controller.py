# modules/giphy_controller.py
import time
import threading
import os
from . import giphy_handler
from . import display_control
from .settings_handler import read_settings

giphy_running = False
GIPHY_DISPLAY_DURATION = 300  # 5 minutes in seconds
DEVICE_ID = read_settings().get("deviceID", "pixel_display_rpi")
mqtt_publish_callback = None  # Placeholder for the callback function

def set_mqtt_publish_callback(callback):
    global mqtt_publish_callback
    mqtt_publish_callback = callback

def giphy_display_loop():
    global giphy_running
    while giphy_running:
        gif_url = giphy_handler.fetch_trending_gif()
        if gif_url:
            local_path = giphy_handler.download_gif(gif_url)
            if local_path:
                filename = os.path.basename(local_path)
                print(f"Displaying Giphy: {filename}")
                display_control.process_image_async(filename, "displayImage", "static/giphy_cache")
                time.sleep(GIPHY_DISPLAY_DURATION + 5)  # Wait for display + a small buffer
                if os.path.exists(local_path):
                    os.remove(local_path)  # Clean up
            else:
                print("Failed to download Giphy.")
        else:
            print("Failed to fetch trending Giphy.")
        if giphy_running:
            time.sleep(10)  # Wait before fetching the next one
    print("Giphy display loop stopped.")

def start_giphy_loop():
    print("Giphy loop started unexpectedly!")
    global giphy_running, mqtt_publish_callback
    if not giphy_running:
        print("Starting Giphy display loop.")
        giphy_running = True
        giphy_thread = threading.Thread(target=giphy_display_loop)
        giphy_thread.daemon = True
        giphy_thread.start()
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/giphy_control/state", "on", retain=True)
    else:
        print("Giphy display loop is already running.")

def stop_giphy_loop():
    global giphy_running, mqtt_publish_callback
    if giphy_running:
        print("Stopping Giphy display loop.")
        giphy_running = False
        if mqtt_publish_callback:
            mqtt_publish_callback(f"switch/{DEVICE_ID}/giphy_control/state", "off", retain=True)
    else:
        print("Giphy display loop is not running.")