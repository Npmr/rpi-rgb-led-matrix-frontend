# modules/mqtt_handler.py
import paho.mqtt.client as mqtt
import json # Import the json module

from .settings_handler import read_settings, save_settings

settings = read_settings()
MQTT_BROKER_IP = settings.get("mqttIP", "YOUR_MQTT_BROKER_IP")
MQTT_BROKER_PORT = int(settings.get("mqttPort", 1883))

def publish_mqtt(topic, payload, retain=False):
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT)
        if payload is not None and not isinstance(payload, (str, bytes, bytearray, int, float)):
            payload = json.dumps(payload) # Convert dictionary payloads to JSON string
        client.publish(topic, payload, retain=retain)
        client.disconnect()
        print(f"Published to topic '{topic}': {payload} (retained: {retain})")
    except Exception as e:
        print(f"Error publishing to MQTT: {e}")

from .mqtt import discovery
from .mqtt import state

publish_binary_sensor_discovery = discovery.publish_binary_sensor_discovery
publish_picture_count_discovery = discovery.publish_picture_count_discovery
publish_gif_count_discovery = discovery.publish_gif_count_discovery
publish_disk_space_discovery = discovery.publish_disk_space_discovery
publish_pixels_per_module_height_discovery = discovery.publish_pixels_per_module_height_discovery
publish_pixels_per_module_width_discovery = discovery.publish_pixels_per_module_width_discovery
publish_chain_length_discovery = discovery.publish_chain_length_discovery

publish_online_status = state.publish_online_status
publish_offline_status = state.publish_offline_status
publish_picture_count = state.publish_picture_count
publish_gif_count = state.publish_gif_count
publish_disk_space = state.publish_disk_space
publish_pixels_per_module_height_state = state.publish_pixels_per_module_height_state
publish_pixels_per_module_width_state = state.publish_pixels_per_module_width_state
publish_chain_length_state = state.publish_chain_length_state

def mqtt_listener(callback_play_media, callback_stop):
    settings = read_settings()
    DEVICE_ID = settings.get("deviceID", "pixel_display_rpi")
    COMPONENT = "media_player"

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            client.subscribe(f"{COMPONENT}/{DEVICE_ID}/command")
            client.subscribe(f"number/{DEVICE_ID}/pixels_per_module_height/set")
            client.subscribe(f"number/{DEVICE_ID}/pixels_per_module_width/set")
            client.subscribe(f"number/{DEVICE_ID}/chain_length/set")
        else:
            print(f"Failed to connect to MQTT Broker, return code {rc}")

    def on_message(client, userdata, msg):
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        if msg.topic == f"{COMPONENT}/{DEVICE_ID}/command":
            try:
                payload = json.loads(msg.payload.decode())
                if "action" in payload:
                    action = payload["action"]
                    if action == "play_media" and "media_id" in payload:
                        callback_play_media(payload["media_id"])
                    elif action == "stop":
                        callback_stop()
            except json.JSONDecodeError:
                print(f"Error decoding JSON payload: {msg.payload.decode()}")
        elif msg.topic == f"number/{DEVICE_ID}/pixels_per_module_height/set":
            try:
                current_settings = read_settings()
                current_settings["heightInPixel"] = msg.payload.decode()
                save_settings(current_settings)
                print(f"Updated heightInPixel to: {msg.payload.decode()}")
                publish_pixels_per_module_height_state()
            except ValueError:
                print(f"Error: Invalid value received for pixelsPerModule: {msg.payload.decode()}")
        elif msg.topic == f"number/{DEVICE_ID}/pixels_per_module_width/set":
            try:
                current_settings = read_settings()
                current_settings["widthInPixel"] = msg.payload.decode()
                save_settings(current_settings)
                print(f"Updated widthInPixel to: {msg.payload.decode()}")
                publish_pixels_per_module_width_state()
            except ValueError:
                print(f"Error: Invalid value received for pixelsPerModule: {msg.payload.decode()}")
        elif msg.topic == f"number/{DEVICE_ID}/chain_length/set":
            try:
                new_chain_length = int(msg.payload.decode())
                current_settings = read_settings()
                current_settings["chainLength"] = str(new_chain_length)
                save_settings(current_settings)
                print(f"Updated chainLength to: {new_chain_length}")
                publish_chain_length_state()
            except ValueError:
                print(f"Error: Invalid value received for chainLength: {msg.payload.decode()}")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return client

    return client