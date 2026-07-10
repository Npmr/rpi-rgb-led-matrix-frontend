# modules/mqtt/state.py
import json
from ..settings_handler import read_settings
from ..media_handler import countMediaTypeAndNumber
from ..system_handler import getFreeDiskSpace

settings = read_settings()
DEVICE_ID = settings.get("deviceID", "pixel_display_rpi")

def _get_publish_mqtt():
    from ..mqtt_handler import publish_mqtt
    return publish_mqtt

def _publish_mqtt(topic, payload, retain=False):
    publish_mqtt = _get_publish_mqtt()
    publish_mqtt(topic, payload, retain=retain)

def publish_online_status():
    payload = "online"
    _publish_mqtt(f"binary_sensor/{DEVICE_ID}/state", payload, retain=True)

def publish_offline_status():
    payload = "offline"
    _publish_mqtt(f"binary_sensor/{DEVICE_ID}/state", payload, retain=True)

def publish_picture_count():
    images, _, _ = countMediaTypeAndNumber()
    _publish_mqtt(f"sensor/{DEVICE_ID}/picture_count", str(len(images)))

def publish_gif_count():
    _, gifs, _ = countMediaTypeAndNumber()
    _publish_mqtt(f"sensor/{DEVICE_ID}/gif_count", str(len(gifs)))

def publish_disk_space():
    freeDiskSpaceInPercent = getFreeDiskSpace()
    _publish_mqtt(f"sensor/{DEVICE_ID}/disk_space", str(round(freeDiskSpaceInPercent[0])))

def publish_device_settings_state():
    settings = read_settings()
    payload = {
        "height": settings.get("heightInPixel"),
        "width": settings.get("widthInPixel"),
        "chain_length": settings.get("chainLength"),
        "parallel_chains": settings.get("parallelChains"),
        "display_slowdown": settings.get("ledSlowdown"),
        "display_image_in_sec": settings.get("playlistTime"),
        "giphy_api_key": settings.get("giphy_api_key"),
        "display_brightness": settings.get("displayBrightness")
    }
    _publish_mqtt(f"sensor/{DEVICE_ID}/device_settings_state", json.dumps(payload))
    print(f"Published device settings state: {payload}")

def publish_device_rotation_settings_state():
    settings = read_settings()
    current_value = settings.get("direction", "vertical") # Replace
    _publish_mqtt(f"sensor/{DEVICE_ID}/device_rotation_settings_state", current_value)
    print(f"Published device_rotation_settings state: {current_value}")

def publish_reboot_button_state(state):
    topic = f"switch/{DEVICE_ID}/reboot/state"
    payload = "ON" if state == "ON" else "OFF"
    _publish_mqtt(topic, payload, retain=True)

def publish_shutdown_button_state(state):
    topic = f"switch/{DEVICE_ID}/shutdown/state"
    payload = "ON" if state == "ON" else "OFF"
    _publish_mqtt(topic, payload, retain=True)

def publish_immich_state(state):
    topic = f"switch/{DEVICE_ID}/immich_control/state"
    payload = "on" if state == "on" else "off"
    _publish_mqtt(topic, payload, retain=True)
    print(f"Published Immich state: {state}")


def publish_text_scroll_state(state, text=""):
    topic = f"switch/{DEVICE_ID}/text_scroll/state"
    payload = "on" if state == "on" else "off"
    _publish_mqtt(topic, payload, retain=True)
    print(f"Published Text Scroll state: {state}")

    # Also publish the current text if provided
    if text:
        text_topic = f"sensor/{DEVICE_ID}/text_scroll_text"
        _publish_mqtt(text_topic, text, retain=True)