import json
import os
import tempfile
import unittest

from modules.bot.bus import BotBus


class TestBotBus(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = self._tmp.name

    def bus(self, **kwargs):
        return BotBus(directory=self.directory, **kwargs)

    def test_publish_stores_metadata_and_drain_returns_it(self):
        bus = self.bus()
        stored = bus.publish(
            {"type": "message", "text": "Hello"},
            source="test", now=100.0,
        )
        self.assertEqual(stored["type"], "message")
        self.assertEqual(stored["_source"], "test")
        self.assertEqual(stored["_receivedAt"], 100.0)
        self.assertTrue(stored["_id"])
        self.assertEqual(bus.count(), 1)

        events = bus.drain(now=101.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["text"], "Hello")
        self.assertEqual(bus.count(), 0)

    def test_drain_is_oldest_first(self):
        bus = self.bus()
        bus.publish({"type": "message", "text": "first"}, now=100.0)
        bus.publish({"type": "message", "text": "second"}, now=100.1)
        events = bus.drain(now=101.0)
        self.assertEqual([event["text"] for event in events], ["first", "second"])

    def test_malformed_files_are_removed(self):
        bus = self.bus()
        bus.ensure_directory()
        with open(os.path.join(self.directory, "broken.json"), "w") as handle:
            handle.write("{not json")
        self.assertEqual(bus.drain(now=100.0), [])
        self.assertEqual(bus.count(), 0)

    def test_stale_events_are_dropped_not_replayed(self):
        bus = self.bus(max_age=300.0)
        bus.publish({"type": "message", "text": "old"}, now=100.0)
        self.assertEqual(bus.drain(now=500.0), [])
        self.assertEqual(bus.count(), 0)

    def test_prune_keeps_the_newest_events(self):
        bus = self.bus(max_events=3)
        for index in range(5):
            bus.publish({"type": "message", "text": str(index)}, now=100.0 + index)
        self.assertEqual(bus.count(), 3)
        events = bus.drain(now=110.0)
        self.assertEqual([event["text"] for event in events], ["2", "3", "4"])

    def test_publish_rejects_non_dict_events(self):
        with self.assertRaises(TypeError):
            self.bus().publish("hello")

    def test_count_on_missing_directory_is_zero(self):
        bus = BotBus(directory=os.path.join(self.directory, "missing"))
        self.assertEqual(bus.count(), 0)


if __name__ == "__main__":
    unittest.main()
