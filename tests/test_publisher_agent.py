import os
import sys
import types
import unittest
from unittest.mock import Mock


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

fake_srt_equalizer = types.ModuleType("srt_equalizer")
fake_srt_equalizer.equalize_srt_file = lambda *args, **kwargs: None
sys.modules.setdefault("srt_equalizer", fake_srt_equalizer)

fake_twitter_module = types.ModuleType("classes.Twitter")
fake_twitter_module.Twitter = object
sys.modules.setdefault("classes.Twitter", fake_twitter_module)

fake_youtube_module = types.ModuleType("classes.YouTube")
fake_youtube_module.YouTube = object
sys.modules.setdefault("classes.YouTube", fake_youtube_module)

fake_post_bridge = types.ModuleType("post_bridge_integration")
fake_post_bridge.maybe_crosspost_youtube_short = lambda *args, **kwargs: None
sys.modules.setdefault("post_bridge_integration", fake_post_bridge)

from agents.publisher_agent import PublisherAgent

sys.modules.pop("post_bridge_integration", None)
sys.modules.pop("classes.Twitter", None)
sys.modules.pop("classes.YouTube", None)


class PublisherAgentTests(unittest.TestCase):
    def test_publish_item_by_id_uses_queue_record(self) -> None:
        item = {
            "id": "item-1",
            "job_id": "job-1",
            "platform": "twitter",
            "account_id": "acc-1",
            "status": "ready",
            "body": "Hello world",
        }

        updated_states = []

        def update_item(_item_id, updates):
            item.update(updates)
            updated_states.append(dict(item))
            return dict(item)

        run_mock = Mock()
        agent = PublisherAgent()
        agent.queue = Mock()
        agent.queue.get_item.return_value = dict(item)
        agent.queue.update_item.side_effect = update_item
        agent.monitor = Mock()
        agent.monitor.start_run.return_value = run_mock
        agent._publish_twitter_item = Mock()

        updated = agent.publish_item_by_id("item-1")

        agent.queue.get_item.assert_called_once_with("item-1")
        agent._publish_twitter_item.assert_called_once()
        self.assertEqual(updated["status"], "published")
        self.assertTrue(updated.get("published_at", "").endswith("Z"))
        self.assertEqual(updated_states[0]["status"], "publishing")
        run_mock.finish.assert_called_once()

    def test_publish_item_by_id_raises_for_missing_record(self) -> None:
        agent = PublisherAgent()
        agent.queue = Mock()
        agent.queue.get_item.return_value = None

        with self.assertRaises(ValueError):
            agent.publish_item_by_id("missing")


if __name__ == "__main__":
    unittest.main()
