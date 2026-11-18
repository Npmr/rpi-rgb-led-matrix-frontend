import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from modules.bot.bus import BotBus
from modules.bot.engine import BotEngine
from modules.bot.reactions import build_reaction
from modules.bot.schedule import is_sleeping, parse_bool, parse_clock


def timestamp(year, month, day, hour, minute=0, zone="UTC"):
    return datetime(
        year, month, day, hour, minute, tzinfo=ZoneInfo(zone)
    ).timestamp()


class TestSchedule(unittest.TestCase):

    def test_overnight_window(self):
        night = timestamp(2026, 1, 1, 23, 30)
        morning = timestamp(2026, 1, 2, 6, 59)
        day = timestamp(2026, 1, 2, 12, 0)
        self.assertTrue(is_sleeping(night, "22:00", "07:00", "UTC", True))
        self.assertTrue(is_sleeping(morning, "22:00", "07:00", "UTC", True))
        self.assertFalse(is_sleeping(day, "22:00", "07:00", "UTC", True))

    def test_window_within_one_day(self):
        self.assertTrue(is_sleeping(timestamp(2026, 1, 1, 13, 0),
                                    "13:00", "14:00", "UTC", True))
        self.assertFalse(is_sleeping(timestamp(2026, 1, 1, 14, 0),
                                     "13:00", "14:00", "UTC", True))

    def test_disabled_and_empty_window(self):
        self.assertFalse(is_sleeping(timestamp(2026, 1, 1, 23, 0),
                                     "22:00", "07:00", "UTC", False))
        self.assertFalse(is_sleeping(timestamp(2026, 1, 1, 23, 0),
                                     "22:00", "22:00", "UTC", True))

    def test_parse_clock_and_bool(self):
        self.assertEqual(parse_clock("07:30"), 450)
        self.assertEqual(parse_clock("bad", "09:15"), 555)
        self.assertEqual(parse_clock("25:00", "09:15"), 555)
        self.assertTrue(parse_bool("on"))
        self.assertTrue(parse_bool("TRUE"))
        self.assertFalse(parse_bool("off"))
        self.assertTrue(parse_bool(None, True))


class TestReactions(unittest.TestCase):

    def test_meeting_defaults(self):
        reaction = build_reaction({"type": "meeting_soon"}, now=100.0)
        self.assertEqual(reaction.mood, "alarmed")
        self.assertEqual(reaction.priority, 7)
        self.assertEqual(reaction.duration, 300.0)
        self.assertEqual(reaction.text, "Meeting soon")

    def test_weather_conditions(self):
        self.assertEqual(build_reaction({"type": "weather", "condition": "rain"}).mood, "sad")
        self.assertEqual(build_reaction({"type": "weather", "condition": "snow"}).mood, "curious")
        self.assertEqual(build_reaction({"type": "weather", "condition": "storm"}).mood, "alarmed")
        self.assertEqual(build_reaction({"type": "weather", "condition": "clear"}).mood, "happy")
        self.assertEqual(build_reaction({"type": "weather", "temp": 35}).mood, "sleepy")
        self.assertEqual(build_reaction({"type": "weather", "temp": -5}).mood, "sad")

    def test_event_overrides(self):
        reaction = build_reaction(
            {
                "type": "message",
                "text": "Dinner",
                "mood": "love",
                "priority": 42,
                "duration": 99999,
            },
            now=100.0,
        )
        self.assertEqual(reaction.mood, "love")
        self.assertEqual(reaction.priority, 10)
        self.assertEqual(reaction.duration, 3600.0)

    def test_message_key_uses_text(self):
        first = build_reaction({"type": "message", "text": "Hello"})
        second = build_reaction({"type": "message", "text": "hello"})
        self.assertEqual(first.key, second.key)

    def test_alias_and_unknown_text_event(self):
        self.assertEqual(build_reaction({"type": "say", "text": "Hi"}).event_type, "message")
        reaction = build_reaction({"type": "something_new", "text": "Hi"})
        self.assertEqual(reaction.event_type, "message")

    def test_invalid_events(self):
        self.assertIsNone(build_reaction(None))
        self.assertIsNone(build_reaction({}))
        self.assertIsNone(build_reaction({"type": "something_new"}))

    def test_sleep_and_wake(self):
        self.assertEqual(build_reaction({"type": "sleep"}).mood, "sleepy")
        self.assertEqual(build_reaction({"type": "wake"}).mood, "idle")


class TestBotEngine(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bus = BotBus(directory=self._tmp.name)

    def engine(self, settings=None, **kwargs):
        base = {"botSleepEnabled": "off", "timezone": "UTC"}
        base.update(settings or {})
        return BotEngine(settings=base, bus=self.bus, **kwargs)

    def test_event_becomes_the_active_reaction(self):
        engine = self.engine()
        engine.handle_event({"type": "meeting_soon"}, now=100.0)
        engine.update(100.0)
        self.assertIsNotNone(engine.active)
        self.assertEqual(engine.state()["mood"], "alarmed")
        self.assertFalse(engine.sleeping)

    def test_reaction_expires_back_to_idle(self):
        engine = self.engine()
        engine.handle_event({"type": "doorbell"}, now=100.0)
        engine.update(100.0)
        engine.update(111.0)
        self.assertIsNone(engine.active)
        self.assertEqual(engine.state()["mood"], "idle")

    def test_higher_priority_preempts_and_old_reaction_resumes(self):
        engine = self.engine()
        engine.handle_event(
            {"type": "message", "text": "low", "priority": 1, "duration": 60},
            now=100.0,
        )
        engine.handle_event({"type": "doorbell"}, now=101.0)
        engine.update(101.0)
        self.assertEqual(engine.active.event_type, "doorbell")
        self.assertEqual(engine.state()["queued"], 1)

        engine.update(112.0)  # doorbell lasts 10s, then the message resumes
        self.assertEqual(engine.active.event_type, "message")
        self.assertEqual(engine.state()["mood"], "curious")

    def test_duplicate_events_are_coalesced(self):
        engine = self.engine()
        engine.handle_event({"type": "message", "text": "Dinner"}, now=100.0)
        engine.handle_event({"type": "message", "text": "Dinner"}, now=100.4)
        engine.update(100.4)
        self.assertEqual(engine.state()["queued"], 0)

    def test_events_are_read_from_the_bus(self):
        engine = self.engine()
        self.bus.publish({"type": "timer_done"}, source="test", now=100.0)
        engine.update(100.0)
        self.assertEqual(engine.active.event_type, "timer_done")
        self.assertEqual(engine.state()["mood"], "excited")

    def test_sleep_schedule_switches_to_sleepy_and_back(self):
        engine = self.engine({
            "botSleepEnabled": "on",
            "botSleepStart": "22:00",
            "botSleepEnd": "07:00",
        })
        night = timestamp(2026, 1, 1, 23, 0)
        engine.update(night)
        self.assertTrue(engine.sleeping)
        self.assertEqual(engine.state()["mood"], "sleepy")

        day = timestamp(2026, 1, 2, 12, 0)
        engine.update(day)
        self.assertFalse(engine.sleeping)
        self.assertEqual(engine.state()["mood"], "idle")

    def test_alarm_wakes_the_bot_during_sleep_hours(self):
        engine = self.engine({
            "botSleepEnabled": "on",
            "botSleepStart": "22:00",
            "botSleepEnd": "07:00",
        })
        night = timestamp(2026, 1, 1, 23, 0)
        engine.update(night)
        self.assertTrue(engine.sleeping)

        engine.handle_event({"type": "alarm"}, now=night + 1)
        engine.update(night + 1)
        self.assertFalse(engine.sleeping)
        self.assertEqual(engine.state()["mood"], "alarmed")

        engine.update(night + 40)  # alarm lasts 30s, then back to sleep
        self.assertTrue(engine.sleeping)
        self.assertEqual(engine.state()["mood"], "sleepy")

    def test_manual_sleep_and_wake(self):
        engine = self.engine()
        engine.handle_event({"type": "sleep"}, now=100.0)
        engine.update(100.0)
        self.assertTrue(engine.sleeping)
        self.assertEqual(engine.state()["mood"], "sleepy")

        engine.handle_event({"type": "wake"}, now=101.0)
        engine.update(101.0)
        self.assertFalse(engine.sleeping)
        self.assertEqual(engine.state()["mood"], "idle")

    def test_sleep_auto_resets_manual_override(self):
        engine = self.engine()
        engine.handle_event({"type": "sleep"}, now=100.0)
        engine.update(100.0)
        engine.handle_event({"type": "sleep", "auto": True}, now=101.0)
        engine.update(101.0)
        self.assertFalse(engine.sleeping)

    def test_zero_duration_stays_until_replaced(self):
        engine = self.engine()
        engine.handle_event({"type": "mood", "mood": "love", "duration": 0}, now=100.0)
        engine.update(100.0)
        engine.update(100000.0)
        self.assertIsNotNone(engine.active)
        self.assertEqual(engine.state()["mood"], "love")

    def test_invalid_event_is_ignored(self):
        engine = self.engine()
        self.assertIsNone(engine.handle_event({}, now=100.0))
        engine.update(100.0)
        self.assertIsNone(engine.active)
        self.assertEqual(engine.state()["mood"], "idle")

    def test_state_contains_active_text_and_expiry(self):
        engine = self.engine()
        engine.handle_event(
            {"type": "message", "text": "Hi", "duration": 30}, now=100.0
        )
        engine.update(110.0)
        state = engine.state()
        self.assertEqual(state["active"]["text"], "Hi")
        self.assertAlmostEqual(state["active"]["expiresIn"], 20.0, places=1)


if __name__ == "__main__":
    unittest.main()
