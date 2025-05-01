# modules/mqtt/state.py
import json

from ..mqtt_handler import publish_mqtt
from ..settings_handler import read_settings
from ..media_handler import countMediaTypeAndNumber
from ..system_handler import getFreeDiskSpace

settings = read_settings()
DEVICE_ID = settings.get("deviceID", "pixel_display_rpi")

def publish_online_status():
    payload = "online"
    publish_mqtt(f"binary_sensor/{DEVICE_ID}/state", payload, retain=True)

def publish_offline_status():
    payload = "offline"
    publish_mqtt(f"binary_sensor/{DEVICE_ID}/state", payload, retain=True)

def publish_picture_count():
    images, _, _ = countMediaTypeAndNumber()
    publish_mqtt(f"sensor/{DEVICE_ID}/picture_count", str(len(images)))

def publish_gif_count():
    _, gifs, _ = countMediaTypeAndNumber()
    publish_mqtt(f"sensor/{DEVICE_ID}/gif_count", str(len(gifs)))

def publish_disk_space():
    freeDiskSpaceInPercent = getFreeDiskSpace()
    publish_mqtt(f"sensor/{DEVICE_ID}/disk_space", str(round(freeDiskSpaceInPercent[0])))

def publish_pixels_per_module_height_state():
    settings = read_settings()
    pixels_per_module = settings.get("heightInPixel", 32) # Default value
    payload = json.dumps({"pixels_per_module": pixels_per_module})
    publish_mqtt(f"sensor/{DEVICE_ID}/pixels_per_module_height_state", payload)
    print(f"Published pixelsPerModule state: {payload}")

def publish_pixels_per_module_width_state():
    settings = read_settings()
    pixels_per_module = settings.get("widthInPixel", 32)  # Default value
    payload = json.dumps({"pixels_per_module": pixels_per_module})
    publish_mqtt(f"sensor/{DEVICE_ID}/pixels_per_module_width_state", payload)
    print(f"Published pixelsPerModule state: {payload}")

def publish_chain_length_state():
    settings = read_settings()
    chain_length = settings.get("chainLength", 1) # Default value
    payload = json.dumps({"chain_length": chain_length})
    publish_mqtt(f"sensor/{DEVICE_ID}/chain_length_state", payload)
    print(f"Published chainLength state: {chain_length}")