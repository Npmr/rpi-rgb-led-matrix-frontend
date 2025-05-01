# modules/mqtt_handler.py
import paho.mqtt.client as mqtt
import json # Import the json module

from .settings_handler import read_settings

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

publish_online_status = state.publish_online_status
publish_offline_status = state.publish_offline_status
publish_picture_count = state.publish_picture_count
publish_gif_count = state.publish_gif_count
publish_disk_space = state.publish_disk_space

def mqtt_listener(callback_play_media, callback_stop):
    settings = read_settings()
    DEVICE_ID = settings.get("deviceID", "pixel_display_rpi")
    COMPONENT = "media_player"

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            client.subscribe(f"{COMPONENT}/{DEVICE_ID}/command")
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

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return client

    return client