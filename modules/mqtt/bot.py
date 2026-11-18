# modules/mqtt/bot.py
"""MQTT ingress, state and Home Assistant discovery for the display bot.

Anything that can talk to the broker can drive the bot:

    bot/<device>/event          JSON bot event (same shape as POST /bot/event)
    bot/<device>/message/set    plain text message
    bot/<device>/mood/set       hold a mood (idle, happy, ...)
    bot/<device>/sleep/set      ON = sleep, OFF = wake
    bot/<device>/display/set    ON = full-screen bot, OFF = stop the display

Home Assistant entities are created automatically: a mood sensor, a sleeping
binary sensor, a mood select, a message text box, a sleep switch and a
full-screen switch.
"""
import json
import threading
import time

from .. import display_control
from ..bot.bus import BotBus
from ..bot.face import MOOD_NAMES
from ..bot.status import read_status
from ..settings_handler import read_settings


def publish_mqtt(topic, payload, retain=False):
    """Publish through the shared MQTT helper.

    Imported lazily because ``mqtt_handler`` imports this module for its
    listener, which would otherwise be a circular import.
    """
    from ..mqtt_handler import publish_mqtt as _publish

    return _publish(topic, payload, retain=retain)

HA_DISCOVERY_PREFIX = "homeassistant"

_TRUTHY = {"ON", "1", "TRUE", "START", "SLEEP", "YES"}

_STATE_THREAD = None
_STATE_INTERVAL = 2.0


def _device_id():
    return read_settings().get("deviceID", "pixel_display_rpi")


def state_topic(device_id=None):
    return f"bot/{device_id or _device_id()}/state"


def _device_info():
    from .discovery import get_device_info

    return get_device_info()


# --- ingress --------------------------------------------------------------

def _parse_event(text):
    """Turn an MQTT payload into a bot event dictionary."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"type": "message", "text": text}

    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return {"type": "message", "text": payload}
    return None


def handle_message(topic, payload, bus=None):
    """Handle one bot MQTT message. Returns True when it was understood."""
    device_id = _device_id()
    prefix = f"bot/{device_id}/"
    if not topic.startswith(prefix):
        return False

    suffix = topic[len(prefix):]
    text = (payload or "").strip()
    bus = bus if bus is not None else BotBus()

    if suffix == "event":
        event = _parse_event(text)
        if event is None:
            return False
        bus.publish(event, source="mqtt")
        return True

    if suffix == "message/set":
        if not text:
            return False
        bus.publish({"type": "message", "text": text}, source="mqtt")
        return True

    if suffix == "mood/set":
        mood = text.lower()
        if mood not in MOOD_NAMES:
            print(f"Bot MQTT: unknown mood {mood!r}, ignoring")
            return False
        # duration 0 keeps the mood until another event replaces it.
        bus.publish(
            {"type": "mood", "mood": mood, "duration": 0}, source="mqtt"
        )
        return True

    if suffix == "sleep/set":
        asleep = text.upper() in _TRUTHY
        bus.publish({"type": "sleep" if asleep else "wake"}, source="mqtt")
        return True

    if suffix == "display/set":
        if text.upper() in _TRUTHY:
            display_control.start_bot_display()
        else:
            display_control.stopProcess()
        return True

    print(f"Bot MQTT: unhandled topic {topic!r}")
    return False


# --- state ----------------------------------------------------------------

def bot_state_payload():
    """Build the JSON state published on the shared state topic."""
    status = read_status()
    mode = status.get("mode")
    if mode not in ("grid", "fullscreen"):
        if display_control.is_bot_running():
            mode = "fullscreen"
        elif display_control.is_grid_running():
            mode = "grid"
        else:
            mode = "stopped"

    return {
        "mood": status.get("mood") or "idle",
        "sleeping": bool(status.get("sleeping")),
        "mode": mode,
        "style": status.get("style"),
        "queued": BotBus().count(),
        "active": status.get("active"),
        "updatedAt": status.get("updatedAt"),
    }


def publish_bot_state():
    payload = bot_state_payload()
    publish_mqtt(state_topic(), json.dumps(payload), retain=True)
    return payload


def start_state_publisher(interval=_STATE_INTERVAL):
    """Publish the bot state every ``interval`` seconds in a daemon thread."""
    global _STATE_THREAD
    if _STATE_THREAD is not None and _STATE_THREAD.is_alive():
        return _STATE_THREAD

    def _loop():
        while True:
            try:
                publish_bot_state()
            except Exception as error:  # keep the thread alive
                print(f"Bot MQTT: could not publish state: {error}")
            time.sleep(max(0.5, float(interval)))

    _STATE_THREAD = threading.Thread(
        target=_loop, name="bot-state-publisher", daemon=True
    )
    _STATE_THREAD.start()
    return _STATE_THREAD


# --- discovery ------------------------------------------------------------

def _availability():
    return {
        "availability_topic": f"binary_sensor/{_device_id()}/state",
        "payload_available": "online",
        "payload_not_available": "offline",
    }


def _publish_discovery(component, object_id, payload):
    payload = dict(payload)
    payload["unique_id"] = f"{_device_id()}_{object_id}"
    topic = f"{HA_DISCOVERY_PREFIX}/{component}/{_device_id()}/{object_id}/config"
    publish_mqtt(topic, payload, retain=True)
    print(f"Published bot {component} discovery info to: {topic}")


def _base(name, icon):
    device_id = _device_id()
    return {
        "device": _device_info(),
        "name": name,
        "state_topic": state_topic(device_id),
        "icon": icon,
        "retain": True,
        **_availability(),
    }


def publish_bot_mood_sensor_discovery():
    payload = _base(f"{_device_name()} Bot Mood", "mdi:emoticon-happy-outline")
    payload["value_template"] = "{{ value_json.mood }}"
    _publish_discovery("sensor", "bot_mood", payload)


def publish_bot_sleeping_discovery():
    payload = _base(f"{_device_name()} Bot Sleeping", "mdi:sleep")
    payload["value_template"] = "{{ 'ON' if value_json.sleeping else 'OFF' }}"
    _publish_discovery("binary_sensor", "bot_sleeping", payload)


def publish_bot_mode_sensor_discovery():
    payload = _base(f"{_device_name()} Bot Mode", "mdi:robot-happy")
    payload["value_template"] = "{{ value_json.mode }}"
    _publish_discovery("sensor", "bot_mode", payload)


def publish_bot_mood_select_discovery():
    device_id = _device_id()
    payload = _base(f"{_device_name()} Bot Mood Preset", "mdi:emoticon-outline")
    payload.update({
        "command_topic": f"bot/{device_id}/mood/set",
        "options": list(MOOD_NAMES),
        "value_template": "{{ value_json.mood }}",
    })
    _publish_discovery("select", "bot_mood_select", payload)


def publish_bot_message_text_discovery():
    device_id = _device_id()
    payload = _base(f"{_device_name()} Bot Message", "mdi:message-text")
    payload.update({
        "command_topic": f"bot/{device_id}/message/set",
        "max": 160,
        "mode": "text",
    })
    _publish_discovery("text", "bot_message", payload)


def publish_bot_sleep_switch_discovery():
    device_id = _device_id()
    payload = _base(f"{_device_name()} Bot Sleep", "mdi:sleep")
    payload.update({
        "command_topic": f"bot/{device_id}/sleep/set",
        "payload_on": "ON",
        "payload_off": "OFF",
        "state_on": "ON",
        "state_off": "OFF",
        "value_template": "{{ 'ON' if value_json.sleeping else 'OFF' }}",
    })
    _publish_discovery("switch", "bot_sleep", payload)


def publish_bot_display_switch_discovery():
    device_id = _device_id()
    payload = _base(f"{_device_name()} Bot Full Screen", "mdi:robot-happy")
    payload.update({
        "command_topic": f"bot/{device_id}/display/set",
        "payload_on": "ON",
        "payload_off": "OFF",
        "state_on": "ON",
        "state_off": "OFF",
        "value_template": "{{ 'ON' if value_json.mode == 'fullscreen' else 'OFF' }}",
    })
    _publish_discovery("switch", "bot_display", payload)


def publish_bot_wake_button_discovery():
    device_id = _device_id()
    payload = _base(f"{_device_name()} Bot Wake", "mdi:weather-sunny")
    payload.update({
        "command_topic": f"bot/{device_id}/event",
        "payload_press": json.dumps({"type": "wake"}),
        "retain": False,
    })
    _publish_discovery("button", "bot_wake", payload)


def _device_name():
    return read_settings().get("deviceName", "Pixel Display Status")


def publish_bot_discovery():
    """Create every bot entity in Home Assistant."""
    publish_bot_mood_sensor_discovery()
    publish_bot_sleeping_discovery()
    publish_bot_mode_sensor_discovery()
    publish_bot_mood_select_discovery()
    publish_bot_message_text_discovery()
    publish_bot_sleep_switch_discovery()
    publish_bot_display_switch_discovery()
    publish_bot_wake_button_discovery()
