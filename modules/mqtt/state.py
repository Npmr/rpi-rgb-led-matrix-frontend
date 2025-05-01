# modules/mqtt/state.py
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
    print(getFreeDiskSpace())
    freeDiskSpaceInPercent = getFreeDiskSpace()
    publish_mqtt(f"sensor/{DEVICE_ID}/disk_space", str(round(freeDiskSpaceInPercent[0])))