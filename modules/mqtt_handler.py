# modules/mqtt_handler.py
import paho.mqtt.client as mqtt
import json
import os
import time
from threading import Timer
from . import giphy_controller  # Import the new controller

from .display_control import stopProcess
from .system_handler import reboot_system, shutdown_system
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

giphy_controller.set_mqtt_publish_callback(publish_mqtt)

publish_binary_sensor_discovery = discovery.publish_binary_sensor_discovery
publish_picture_count_discovery = discovery.publish_picture_count_discovery
publish_gif_count_discovery = discovery.publish_gif_count_discovery
publish_disk_space_discovery = discovery.publish_disk_space_discovery
# publish_device_settings_sensor_discovery = discovery.publish_device_settings_sensor_discovery
publish_device_rotation_settings_discovery = discovery.publish_device_rotation_settings_discovery
publish_reboot_button_discovery = discovery.publish_reboot_button_discovery
publish_shutdown_button_discovery = discovery.publish_shutdown_button_discovery
publish_giphy_button_start_discovery = discovery.publish_giphy_start_button_discovery
publish_giphy_button_stop_discovery = discovery.publish_giphy_stop_button_discovery
publish_settings_pixel_height_discovery = discovery.publish_settings_pixel_height_discovery
publish_settings_pixel_width_discovery = discovery.publish_settings_pixel_width_discovery
publish_settings_chain_length_discovery = discovery.publish_settings_chain_length_discovery
publish_settings_parallel_chains_discovery = discovery.publish_settings_parallel_chains_discovery
publish_settings_display_slowdown_discovery = discovery.publish_settings_display_slowdown_discovery
publish_settings_display_image_in_sec_discovery = discovery.publish_settings_display_image_in_sec_discovery
publish_settings_display_brightness_discovery = discovery.publish_settings_display_brightness_discovery

publish_online_status = state.publish_online_status
publish_offline_status = state.publish_offline_status
publish_picture_count = state.publish_picture_count
publish_gif_count = state.publish_gif_count
publish_disk_space = state.publish_disk_space
publish_device_settings_state = state.publish_device_settings_state
publish_device_rotation_settings_state = state.publish_device_rotation_settings_state
publish_reboot_button_state = state.publish_reboot_button_state
publish_shutdown_button_state = state.publish_shutdown_button_state

def mqtt_listener(callback_play_media, callback_stop):
    settings = read_settings()
    DEVICE_ID = settings.get("deviceID", "pixel_display_rpi")
    COMPONENT = "media_player"

    _last_giphy_start_time = 0.0
    _giphy_start_throttle_interval = 2.5  # Adjust as needed (seconds)
    _giphy_start_pending = False
    _giphy_start_timer = None
    _processed_payloads = set()
    _payloads_cleanup_interval = 30  # Clear payloads every 5 minutes (adjust as needed)
    _payloads_cleanup_timer = None

    def _clear_processed_payloads():
        nonlocal _processed_payloads, _payloads_cleanup_timer
        print("Clearing _processed_payloads set.")
        _processed_payloads.clear()
        _payloads_cleanup_timer = Timer(_payloads_cleanup_interval, _clear_processed_payloads)
        _payloads_cleanup_timer.daemon = True
        _payloads_cleanup_timer.start()

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            client.subscribe(f"{COMPONENT}/{DEVICE_ID}/command")
            client.subscribe(f"number/{DEVICE_ID}/pixels_per_module_height/set")
            client.subscribe(f"number/{DEVICE_ID}/pixels_per_module_width/set")
            client.subscribe(f"number/{DEVICE_ID}/parallel_chains/set")
            client.subscribe(f"number/{DEVICE_ID}/chain_length/set")
            client.subscribe(f"number/{DEVICE_ID}/display_image_in_sec/set")
            client.subscribe(f"number/{DEVICE_ID}/display_slowdown/set")
            client.subscribe(f"select/{DEVICE_ID}/device_rotation_settings/set")
            client.subscribe(f"button/{DEVICE_ID}/reboot/press")
            client.subscribe(f"button/{DEVICE_ID}/shutdown/press")
            client.subscribe(f"button/{DEVICE_ID}/giphy_start/press")
            client.subscribe(f"button/{DEVICE_ID}/giphy_stop/press")
            _clear_processed_payloads() # Start the cleanup timer on connect
        else:
            print(f"Failed to connect to MQTT Broker, return code {rc}")

    def _throttled_start_giphy():
        nonlocal _last_giphy_start_time, _giphy_start_pending, _giphy_start_timer
        giphy_controller.start_giphy_loop()
        _last_giphy_start_time = time.time()
        _giphy_start_pending = False
        _giphy_start_timer = None

    def on_message(client, userdata, msg):
        nonlocal _last_giphy_start_time, _giphy_start_pending, _giphy_start_timer, _processed_payloads
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        try:
            payload = msg.payload.decode()
            payload_id = f"{msg.topic}-{payload}"  # Create a unique ID based on topic and payload
            if payload_id not in _processed_payloads:
                _processed_payloads.add(payload_id)
                if msg.topic == f"{COMPONENT}/{DEVICE_ID}/command":
                    try:
                        json_payload = json.loads(payload)
                        if "action" in json_payload:
                            action = json_payload["action"]
                            if action == "play_media" and "media_id" in json_payload:
                                callback_play_media(json_payload["media_id"])
                            elif action == "stop":
                                callback_stop()
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON payload: {payload}")
                elif msg.topic == f"number/{DEVICE_ID}/pixels_per_module_height/set":
                    try:
                        current_settings = read_settings()
                        current_settings["heightInPixel"] = payload
                        save_settings(current_settings)
                        print(f"Updated heightInPixel to: {payload}")
                        discovery.publish_device_settings_sensor_discovery()  # Re-publish state
                    except ValueError:
                        print(f"Error: Invalid value received for pixelsPerModule: {payload}")
                elif msg.topic == f"number/{DEVICE_ID}/pixels_per_module_width/set":
                    try:
                        current_settings = read_settings()
                        current_settings["widthInPixel"] = payload
                        save_settings(current_settings)
                        print(f"Updated widthInPixel to: {payload}")
                        discovery.publish_device_settings_sensor_discovery()  # Re-publish state
                    except ValueError:
                        print(f"Error: Invalid value received for pixelsPerModule: {payload}")
                elif msg.topic == f"number/{DEVICE_ID}/chain_length/set":
                    try:
                        new_chain_length = int(payload)
                        current_settings = read_settings()
                        current_settings["chainLength"] = str(new_chain_length)
                        save_settings(current_settings)
                        print(f"Updated chainLength to: {new_chain_length}")
                        discovery.publish_device_settings_sensor_discovery()  # Re-publish state
                    except ValueError:
                        print(f"Error: Invalid value received for chainLength: {payload}")
                elif msg.topic == f"number/{DEVICE_ID}/parallel_chains/set":
                    try:
                        new_chain_length = int(payload)
                        current_settings = read_settings()
                        current_settings["parallelChains"] = str(new_chain_length)
                        save_settings(current_settings)
                        print(f"Updated parallelChains to: {new_chain_length}")
                        discovery.publish_device_settings_sensor_discovery()  # Re-publish state
                    except ValueError:
                        print(f"Error: Invalid value received for chainLength: {payload}")
                elif msg.topic == f"number/{DEVICE_ID}/display_image_in_sec/set":
                    try:
                        new_chain_length = int(payload)
                        current_settings = read_settings()
                        current_settings["playlistTime"] = str(new_chain_length)
                        save_settings(current_settings)
                        print(f"Updated display_image_in_sec to: {new_chain_length}")
                        discovery.publish_device_settings_sensor_discovery()  # Re-publish state
                    except ValueError:
                        print(f"Error: Invalid value received for chainLength: {payload}")
                elif msg.topic == f"number/{DEVICE_ID}/display_slowdown/set":
                    try:
                        new_chain_length = int(payload)
                        current_settings = read_settings()
                        current_settings["ledSlowdown"] = str(new_chain_length)
                        save_settings(current_settings)
                        print(f"Updated display_slowdown to: {new_chain_length}")
                        discovery.publish_device_settings_sensor_discovery()  # Re-publish state
                    except ValueError:
                        print(f"Error: Invalid value received for chainLength: {payload}")
                elif msg.topic == f"select/{DEVICE_ID}/device_rotation_settings/set":
                    try:
                        new_value = payload
                        current_settings = read_settings()
                        current_settings["direction"] = new_value
                        save_settings(current_settings)
                        print(f"Updated device_rotation_settings to: {new_value}")
                        discovery.publish_device_rotation_settings_state()  # Re-publish state
                    except Exception as e:
                        print(f"Error processing select command: {e}")
                elif msg.topic == f"button/{DEVICE_ID}/reboot/press":
                    if payload == "REBOOT":
                        print("Received reboot button press from Home Assistant.")
                        reboot_system()
                elif msg.topic == f"button/{DEVICE_ID}/shutdown/press":
                    if payload == "SHUTDOWN":
                        print("Received shutdown button press from Home Assistant.")
                        shutdown_system()
                elif msg.topic == f"button/{DEVICE_ID}/giphy_start/press":
                    if not _giphy_start_pending and (
                            time.time() - _last_giphy_start_time >= _giphy_start_throttle_interval):
                        _giphy_start_pending = True
                        if _giphy_start_timer and _giphy_start_timer.is_alive():
                            _giphy_start_timer.cancel()
                        _giphy_start_timer = Timer(0.1, _throttled_start_giphy)  # Small delay
                        _giphy_start_timer.start()
                    elif _giphy_start_pending:
                        print("Giphy start command already pending, ignoring.")
                    else:
                        print("Giphy start command throttled.")
                elif msg.topic == f"button/{DEVICE_ID}/giphy_stop/press":
                    stopProcess()
                    giphy_controller.stop_giphy_loop()
            else:
                print(f"Ignoring duplicate message on topic `{msg.topic}` with payload `{payload}`")
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT)
        _payloads_cleanup_timer = Timer(_payloads_cleanup_interval, _clear_processed_payloads)
        _payloads_cleanup_timer.daemon = True
        _payloads_cleanup_timer.start()
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return client

    return client