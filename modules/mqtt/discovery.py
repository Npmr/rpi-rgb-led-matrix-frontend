# modules/mqtt/discovery.py
from ..mqtt_handler import publish_mqtt
from ..settings_handler import read_settings
from ..info_handler import read_infos
import socket

settings = read_settings()
HA_DISCOVERY_PREFIX = "homeassistant"
DEVICE_ID = settings.get("deviceID", "pixel_display_rpi")
DEVICE_NAME = settings.get("deviceName", "Pixel Display Status")

def get_device_url():
    hostname = socket.gethostname()
    ipaddress = socket.gethostbyname(hostname)
    ip_address = settings.get("deviceIP", ipaddress)
    port = settings.get("port", "5000")
    return f"http://{ip_address}:{port}"

def get_device_info():
    return {
        "identifiers": [DEVICE_ID],
        "name": DEVICE_NAME,
        "manufacturer": "Raspberry Pi",
        "model": "N.P.M.R RGB Led Matrix Frontend",
        "sw_version": read_infos().get('currentApplicationVersion', 'unknown'),
        "configuration_url": get_device_url()
    }

def publish_binary_sensor_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/binary_sensor/{DEVICE_ID}/config"
    discovery_payload = {
        "device": device_info,
        "name": DEVICE_NAME,
        "unique_id": f"{DEVICE_ID}_status_sensor",
        "state_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_on": "online",
        "payload_off": "offline",
        "device_class": "connectivity",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published binary sensor discovery info to: {discovery_topic}")

def publish_picture_count_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/picture_count/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Picture Count",
        "unique_id": f"{DEVICE_ID}_picture_count",
        "state_topic": f"sensor/{DEVICE_ID}/picture_count",
        "value_template": "{{ value }}", # Expecting raw value
        "unit_of_measurement": "pictures",
        "icon": "mdi:image-multiple",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published picture count discovery info to: {discovery_topic}")

def publish_gif_count_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/gif_count/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Gif Count",
        "unique_id": f"{DEVICE_ID}_gif_count",
        "state_topic": f"sensor/{DEVICE_ID}/gif_count",
        "value_template": "{{ value }}", # Expecting raw value
        "unit_of_measurement": "gifs",
        "icon": "mdi:image-multiple",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published gif count discovery info to: {discovery_topic}")

def publish_disk_space_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/disk_space/config"
    discovery_payload = {
        "device": device_info,
        "name": f"Disk Space in use",
        "unique_id": f"{DEVICE_ID}_disk_space",
        "state_topic": f"sensor/{DEVICE_ID}/disk_space",
        "value_template": "{{ value }}", # Expecting raw value
        "unit_of_measurement": "%",
        "icon": "mdi:image-multiple",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published disk space discovery info to: {discovery_topic}")

def publish_pixels_per_module_height_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/pixels_per_module_height/config"
    discovery_payload = {
        "device": device_info,
        "name": f"Pixels Per Module Height",
        "unique_id": f"{DEVICE_ID}_pixels_per_module_height",
        "command_topic": f"number/{DEVICE_ID}/pixels_per_module_height/set",
        "state_topic": f"sensor/{DEVICE_ID}/pixels_per_module_height_state", # Optional: to display current state
        "value_template": "{{ value_json.pixels_per_module }}", # If publishing state as JSON
        "min": 16,  # Example minimum value
        "max": 256, # Example maximum value
        "step": 16, # Example step value
        "default": 32,
        "unit_of_measurement": "int",
        "icon": "mdi:led-strip",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "mode": "box"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixels per module discovery info to: {discovery_topic}")

def publish_pixels_per_module_width_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/pixels_per_module_width/config"
    discovery_payload = {
        "device": device_info,
        "name": f"Pixels Per Module Width",
        "unique_id": f"{DEVICE_ID}_pixels_per_module_width",
        "command_topic": f"number/{DEVICE_ID}/pixels_per_module_width/set",
        "state_topic": f"sensor/{DEVICE_ID}/pixels_per_module_width_state", # Optional: to display current state
        "value_template": "{{ value_json.pixels_per_module }}", # If publishing state as JSON
        "min": 16,  # Example minimum value
        "max": 256, # Example maximum value
        "step": 16, # Example step value
        "default": 32,
        "unit_of_measurement": "int",
        "icon": "mdi:led-strip",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "mode": "box"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixels per module discovery info to: {discovery_topic}")

def publish_chain_length_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/chain_length/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Chain Length",
        "unique_id": f"{DEVICE_ID}_chain_length",
        "command_topic": f"number/{DEVICE_ID}/chain_length/set",
        "state_topic": f"sensor/{DEVICE_ID}/chain_length_state",
        "value_template": "{{ value_json.chain_length }}",
        "min": 1,
        "max": 24,  # Example maximum chain length
        "step": 1,
        "default": 1,
        "unit_of_measurement": "int",
        "icon": "mdi:link",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "mode": "box"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published chain length discovery info to: {discovery_topic}")