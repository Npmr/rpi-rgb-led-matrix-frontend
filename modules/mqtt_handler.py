# modules/mqtt_handler.py
import paho.mqtt.client as mqtt
import json
from .info_handler import read_infos
from .settings_handler import read_settings

settings = read_settings()

HA_DISCOVERY_PREFIX = "homeassistant"
COMPONENT = "binary_sensor"  # Changed component type
DEVICE_ID = settings.get("deviceID", "pixel_display_rpi") # Use get with default
DEVICE_NAME = settings.get("deviceName", "Pixel Display Status") # Use get with default

MQTT_BROKER_IP = settings.get("mqttIP", "YOUR_MQTT_BROKER_IP") # Use get with default
MQTT_BROKER_PORT = int(settings.get("mqttPort", 1883)) # Use get with default

MQTT_STATE_TOPIC = f"{COMPONENT}/{DEVICE_ID}/state"  # Using the sensor's state topic

def publish_mqtt(topic, payload, retain=False):
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT)
        client.publish(topic, json.dumps(payload), retain=retain)
        client.disconnect()
        print(f"Published to topic '{topic}': {json.dumps(payload)}")
    except Exception as e:
        print(f"Error publishing to MQTT: {e}")

def publish_binary_sensor_discovery():
    device_info = {
        "identifiers": [DEVICE_ID],
        "name": DEVICE_NAME,
        "manufacturer": "Raspberry Pi",
        "model": "N.P.M.R RGB Led Matrix Frontend",
        "sw_version": read_infos().get('currentApplicationVersion', 'unknown'),
    }

    discovery_topic = f"{HA_DISCOVERY_PREFIX}/{COMPONENT}/{DEVICE_ID}/config"
    discovery_payload = {
        "device": device_info,
        "name": DEVICE_NAME,
        "unique_id": f"{DEVICE_ID}_status_sensor",
        "state_topic": MQTT_STATE_TOPIC,
        "payload_on": "online",
        "payload_off": "offline",
        "device_class": "connectivity",
        "availability_topic": MQTT_STATE_TOPIC, # Use the same state topic for availability
        "payload_available": "online",
        "payload_not_available": "offline",
        "retain": True # Retain the discovery message
    }
    publish_mqtt(discovery_topic, discovery_payload, retain=True)
    print(f"Published MQTT discovery info to: {discovery_topic}")

def publish_online_status():
    payload = {"state": "online"}
    publish_mqtt(MQTT_STATE_TOPIC, payload, retain=True)

def publish_offline_status():
    payload = {"state": "offline"}
    publish_mqtt(MQTT_STATE_TOPIC, payload, retain=True)

def mqtt_listener(callback_play_media, callback_stop):
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            client.subscribe(f"{COMPONENT}/{DEVICE_ID}/command") # Still subscribe to the media_player command topic
        else:
            print(f"Failed to connect to MQTT Broker, return code {rc}")

    def on_message(client, userdata, msg):
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        if msg.topic == f"{COMPONENT}/{DEVICE_ID}/command": # Still listen for media_player commands
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