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

def publish_device_rotation_settings_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/select/{DEVICE_ID}/device_rotation_settings/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Device Rotation",  # Replace with the actual name
        "unique_id": f"{DEVICE_ID}device_rotation_settings", # Replace with a unique ID
        "command_topic": f"select/{DEVICE_ID}/device_rotation_settings/set",
        "state_topic": f"sensor/{DEVICE_ID}/device_rotation_settings_state", # Topic to publish the current state
        "options": ["vertical", "verticalTurned", "horizontal", "horizontalTurned"], # Replace with your four actual values
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "entity_category": "config"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published your select setting discovery info to: {discovery_topic}")

def publish_reboot_button_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/button/{DEVICE_ID}/reboot/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Reboot",
        "unique_id": f"{DEVICE_ID}_reboot_button",
        "command_topic": f"button/{DEVICE_ID}/reboot/press",
        "payload_press": "REBOOT",
        "icon": "mdi:restart",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": False # Buttons don't usually have a state to retain
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published reboot button discovery info to: {discovery_topic}")

def publish_shutdown_button_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/button/{DEVICE_ID}/shutdown/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Shutdown",
        "unique_id": f"{DEVICE_ID}_shutdown_button",
        "command_topic": f"button/{DEVICE_ID}/shutdown/press",
        "payload_press": "SHUTDOWN",
        "icon": "mdi:power",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": False # Buttons don't usually have a state to retain
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published shutdown button discovery info to: {discovery_topic}")

def publish_giphy_start_button_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/button/{DEVICE_ID}/giphy_start/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Start Giphy Loop",
        "unique_id": f"{DEVICE_ID}_giphy_start_button",
        "command_topic": f"button/{DEVICE_ID}/giphy_start/press",
        "payload_press": "START",
        "icon": "mdi:play",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": False
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published Giphy start button discovery info to: {discovery_topic}")

def publish_giphy_stop_button_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/button/{DEVICE_ID}/giphy_stop/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Stop / Clear Display",
        "unique_id": f"{DEVICE_ID}_giphy_stop_button",
        "command_topic": f"button/{DEVICE_ID}/giphy_stop/press",
        "payload_press": "STOP",
        "icon": "mdi:stop",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": False
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published Giphy stop button discovery info to: {discovery_topic}")

def publish_settings_pixel_height_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/pixels_per_module_height/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Module Pixel Height",
        "unique_id": f"{DEVICE_ID}_module_pixel_height",
        "state_topic": f"sensor/{DEVICE_ID}/pixels_per_module_height_state",
        "value_template": "{{ value_json.height }}",
        "command_topic": f"number/{DEVICE_ID}/pixels_per_module_height/set",
        "min": 16,  # Set appropriate minimum
        "max": 128, # Set appropriate maximum
        "step": 16, # Set appropriate step
        "unit_of_measurement": "pixels",
        "icon": "mdi:arrow-vertical",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "entity_category": "config"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixel height discovery info to: {discovery_topic}")

def publish_settings_pixel_width_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/pixels_per_module_width/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Module Pixel Width",
        "unique_id": f"{DEVICE_ID}_module_pixel_width",
        "state_topic": f"sensor/{DEVICE_ID}/pixels_per_module_width_state",
        "value_template": "{{ value_json.width }}",
        "command_topic": f"number/{DEVICE_ID}/pixels_per_module_width/set",
        "min": 16,  # Set appropriate minimum
        "max": 128, # Set appropriate maximum
        "step": 16, # Set appropriate step
        "unit_of_measurement": "pixels",
        "icon": "mdi:arrow-vertical",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "entity_category": "config"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixel width discovery info to: {discovery_topic}")

def publish_settings_chain_length_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/chain_length/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Module Chain Length",
        "unique_id": f"{DEVICE_ID}_chain_length",
        "state_topic": f"sensor/{DEVICE_ID}/chain_length_state",
        "value_template": "{{ value_json.chain_length }}",
        "command_topic": f"number/{DEVICE_ID}/chain_length/set",
        "min": 1,  # Set appropriate minimum
        "max": 24, # Set appropriate maximum
        "step": 1, # Set appropriate step
        "unit_of_measurement": "pixels",
        "icon": "mdi:arrow-vertical",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "entity_category": "config"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixel height discovery info to: {discovery_topic}")

def publish_settings_parallel_chains_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/parallel_chains/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Parallel Chains",
        "unique_id": f"{DEVICE_ID}_parallel_chains",
        "state_topic": f"sensor/{DEVICE_ID}/parallel_chains_state",
        "value_template": "{{ value_json.parallel_chains }}",
        "command_topic": f"number/{DEVICE_ID}/parallel_chains/set",
        "min": 1,  # Set appropriate minimum
        "max": 3, # Set appropriate maximum
        "step": 1, # Set appropriate step
        "unit_of_measurement": "int",
        "icon": "mdi:arrow-vertical",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "entity_category": "config"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixel height discovery info to: {discovery_topic}")

def publish_settings_display_slowdonw_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/display_slowdown/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Display Slowdown",
        "unique_id": f"{DEVICE_ID}_display_slowdown",
        "state_topic": f"sensor/{DEVICE_ID}/display_slowdown_state",
        "value_template": "{{ value_json.display_slowdown }}",
        "command_topic": f"number/{DEVICE_ID}/display_slowdown/set",
        "min": 1,  # Set appropriate minimum
        "max": 3, # Set appropriate maximum
        "step": 1, # Set appropriate step
        "unit_of_measurement": "int",
        "icon": "mdi:arrow-vertical",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "entity_category": "config"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixel height discovery info to: {discovery_topic}")

def publish_settings_display_image_in_sec_discovery():
    device_info = get_device_info()
    discovery_topic = f"{HA_DISCOVERY_PREFIX}/number/{DEVICE_ID}/display_image_in_sec/config"
    discovery_payload = {
        "device": device_info,
        "name": f"{DEVICE_NAME} Display Slowdown",
        "unique_id": f"{DEVICE_ID}_display_image_in_sec",
        "state_topic": f"sensor/{DEVICE_ID}/display_image_in_sec_state",
        "value_template": "{{ value_json.display_image_in_sec }}",
        "command_topic": f"number/{DEVICE_ID}/display_image_in_sec/set",
        "min": 30,  # Set appropriate minimum
        "max": 600, # Set appropriate maximum
        "step": 1, # Set appropriate step
        "unit_of_measurement": "int",
        "icon": "mdi:arrow-vertical",
        "availability_topic": f"binary_sensor/{DEVICE_ID}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True,
        "entity_category": "config"
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published pixel height discovery info to: {discovery_topic}")