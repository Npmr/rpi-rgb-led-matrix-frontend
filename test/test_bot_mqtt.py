import tempfile
import unittest
from unittest.mock import patch

from modules.bot.bus import BotBus
from modules.mqtt import bot as bot_mqtt

SETTINGS = {"deviceID": "test_pi", "deviceName": "Test Panel"}


class TestBotMqttIngress(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bus = BotBus(directory=self._tmp.name)
        self._settings = patch.object(
            bot_mqtt, "read_settings", return_value=dict(SETTINGS)
        )
        self._settings.start()
        self.addCleanup(self._settings.stop)

    def publish(self, suffix, payload):
        return bot_mqtt.handle_message(
            f"bot/test_pi/{suffix}", payload, bus=self.bus
        )

    def drain(self):
        return self.bus.drain(now=__import__("time").time())

    def test_json_event_is_queued(self):
        self.assertTrue(self.publish(
            "event", '{"type": "meeting_soon", "text": "Standup"}'
        ))
        events = self.drain()
        self.assertEqual(events[0]["type"], "meeting_soon")
        self.assertEqual(events[0]["text"], "Standup")
        self.assertEqual(events[0]["_source"], "mqtt")

    def test_plain_text_event_becomes_a_message(self):
        self.assertTrue(self.publish("event", "Dinner is ready"))
        self.assertEqual(self.drain()[0]["text"], "Dinner is ready")

    def test_empty_event_is_ignored(self):
        self.assertFalse(self.publish("event", "   "))

    def test_message_topic(self):
        self.assertTrue(self.publish("message/set", "Hello there"))
        event = self.drain()[0]
        self.assertEqual(event["type"], "message")
        self.assertEqual(event["text"], "Hello there")

    def test_mood_topic_is_held(self):
        self.assertTrue(self.publish("mood/set", "happy"))
        event = self.drain()[0]
        self.assertEqual(event["mood"], "happy")
        self.assertEqual(event["duration"], 0)

    def test_unknown_mood_is_rejected(self):
        self.assertFalse(self.publish("mood/set", "smug"))
        self.assertEqual(self.drain(), [])

    def test_sleep_and_wake_topics(self):
        self.assertTrue(self.publish("sleep/set", "ON"))
        self.assertEqual(self.drain()[0]["type"], "sleep")
        self.assertTrue(self.publish("sleep/set", "OFF"))
        self.assertEqual(self.drain()[0]["type"], "wake")

    def test_unknown_topic_is_rejected(self):
        self.assertFalse(bot_mqtt.handle_message(
            "bot/test_pi/nope", "x", bus=self.bus
        ))
        self.assertFalse(bot_mqtt.handle_message(
            "bot/other_pi/event", "x", bus=self.bus
        ))

    @patch("modules.display_control.start_bot_display")
    def test_display_on_starts_the_full_screen_renderer(self, start):
        self.assertTrue(self.publish("display/set", "ON"))
        start.assert_called_once_with()

    @patch("modules.display_control.stopProcess")
    def test_display_off_stops_the_renderer(self, stop):
        self.assertTrue(self.publish("display/set", "OFF"))
        stop.assert_called_once_with()


class TestBotMqttDiscovery(unittest.TestCase):

    def setUp(self):
        self._settings = patch.object(
            bot_mqtt, "read_settings", return_value=dict(SETTINGS)
        )
        self._settings.start()
        self.addCleanup(self._settings.stop)
        self._info = patch.object(bot_mqtt, "_device_info", return_value={})
        self._info.start()
        self.addCleanup(self._info.stop)
        self.published = []

        def fake_publish(topic, payload, retain=False):
            self.published.append((topic, payload))

        self._publish = patch.object(bot_mqtt, "publish_mqtt", fake_publish)
        self._publish.start()
        self.addCleanup(self._publish.stop)

    def topics(self):
        return {topic: payload for topic, payload in self.published}

    def test_discovery_creates_all_entities(self):
        bot_mqtt.publish_bot_discovery()
        topics = self.topics()
        expected = [
            "homeassistant/sensor/test_pi/bot_mood/config",
            "homeassistant/binary_sensor/test_pi/bot_sleeping/config",
            "homeassistant/sensor/test_pi/bot_mode/config",
            "homeassistant/select/test_pi/bot_mood_select/config",
            "homeassistant/text/test_pi/bot_message/config",
            "homeassistant/switch/test_pi/bot_sleep/config",
            "homeassistant/switch/test_pi/bot_display/config",
            "homeassistant/button/test_pi/bot_wake/config",
        ]
        for topic in expected:
            with self.subTest(topic=topic):
                self.assertIn(topic, topics)

        for topic, payload in topics.items():
            with self.subTest(topic=topic):
                self.assertEqual(
                    payload["state_topic"], "bot/test_pi/state"
                )
                self.assertTrue(payload["unique_id"].startswith("test_pi_"))

    def test_mood_select_offers_every_mood(self):
        bot_mqtt.publish_bot_discovery()
        payload = self.topics()[
            "homeassistant/select/test_pi/bot_mood_select/config"
        ]
        self.assertIn("happy", payload["options"])
        self.assertIn("alarmed", payload["options"])
        self.assertEqual(
            payload["command_topic"], "bot/test_pi/mood/set"
        )

    def test_display_switch_reads_the_mode(self):
        bot_mqtt.publish_bot_discovery()
        payload = self.topics()[
            "homeassistant/switch/test_pi/bot_display/config"
        ]
        self.assertEqual(payload["command_topic"], "bot/test_pi/display/set")
        self.assertIn("fullscreen", payload["value_template"])

    def test_message_text_entity(self):
        bot_mqtt.publish_bot_discovery()
        payload = self.topics()[
            "homeassistant/text/test_pi/bot_message/config"
        ]
        self.assertEqual(payload["command_topic"], "bot/test_pi/message/set")
        self.assertEqual(payload["max"], 160)


class TestBotMqttState(unittest.TestCase):

    def setUp(self):
        self._settings = patch.object(
            bot_mqtt, "read_settings", return_value=dict(SETTINGS)
        )
        self._settings.start()
        self.addCleanup(self._settings.stop)

    @patch.object(bot_mqtt, "read_status")
    @patch.object(bot_mqtt.BotBus, "count", return_value=3)
    @patch("modules.display_control.is_bot_running", return_value=False)
    @patch("modules.display_control.is_grid_running", return_value=True)
    def test_payload_uses_renderer_status(
        self, _grid, _bot, _count, status
    ):
        status.return_value = {
            "mood": "alarmed",
            "sleeping": False,
            "mode": "fullscreen",
            "style": "robot",
        }
        payload = bot_mqtt.bot_state_payload()
        self.assertEqual(payload["mood"], "alarmed")
        self.assertEqual(payload["mode"], "fullscreen")
        self.assertEqual(payload["queued"], 3)

    @patch.object(bot_mqtt, "read_status", return_value={})
    @patch.object(bot_mqtt.BotBus, "count", return_value=0)
    @patch("modules.display_control.is_bot_running", return_value=False)
    @patch("modules.display_control.is_grid_running", return_value=False)
    def test_payload_falls_back_to_process_state(
        self, _grid, _bot, _count, _status
    ):
        payload = bot_mqtt.bot_state_payload()
        self.assertEqual(payload["mode"], "stopped")
        self.assertEqual(payload["mood"], "idle")
        self.assertFalse(payload["sleeping"])

    @patch.object(bot_mqtt, "publish_mqtt")
    def test_publish_uses_the_state_topic(self, publish):
        bot_mqtt.publish_bot_state()
        topic, payload = publish.call_args[0][:2]
        self.assertEqual(topic, "bot/test_pi/state")
        self.assertIn("mood", __import__("json").loads(payload))
        self.assertTrue(publish.call_args[1]["retain"])


if __name__ == "__main__":
    unittest.main()
