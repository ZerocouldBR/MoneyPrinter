import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

fake_srt_equalizer = types.ModuleType("srt_equalizer")
fake_srt_equalizer.equalize_srt_file = lambda *args, **kwargs: None
sys.modules.setdefault("srt_equalizer", fake_srt_equalizer)

from agents.planner_agent import PlannerAgent
from services.queue_service import QueueService
from services.topic_history_service import TopicHistoryService


class PlannerAndQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()

        root_patchers = [
            patch("services.queue_service.ROOT_DIR", self.tempdir.name),
            patch("services.topic_history_service.ROOT_DIR", self.tempdir.name),
        ]
        for patcher in root_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.queue = QueueService()
        self.topic_history = TopicHistoryService()
        self.planner = PlannerAgent()
        self.planner.topic_history = self.topic_history

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_planner_rotates_topics_round_robin(self) -> None:
        job = {
            "id": "yt-economia",
            "platform": "youtube",
            "topic_mode": "scheduled",
            "topics": ["economia", "selic", "dólar"],
        }

        first = self.planner.plan(job)
        second = self.planner.plan(job)
        third = self.planner.plan(job)
        fourth = self.planner.plan(job)

        self.assertEqual(first["topic"], "economia")
        self.assertEqual(second["topic"], "selic")
        self.assertEqual(third["topic"], "dólar")
        self.assertEqual(fourth["topic"], "economia")

    def test_queue_returns_oldest_ready_item(self) -> None:
        self.queue.add_item(
            {
                "id": "2",
                "job_id": "job-1",
                "platform": "youtube",
                "account_id": "acc",
                "status": "ready",
                "created_at": "2026-06-16T09:00:00Z",
                "topic": "mais novo",
            }
        )
        self.queue.add_item(
            {
                "id": "1",
                "job_id": "job-1",
                "platform": "youtube",
                "account_id": "acc",
                "status": "ready",
                "created_at": "2026-06-16T08:00:00Z",
                "topic": "mais antigo",
            }
        )

        item = self.queue.find_next_ready_item("youtube", "job-1")
        self.assertIsNotNone(item)
        self.assertEqual(item["id"], "1")

    def test_planner_uses_news_story_in_hybrid_mode(self) -> None:
        job = {
            "id": "yt-news",
            "platform": "youtube",
            "topic_mode": "hybrid",
            "topics": ["economia", "selic"],
            "news_sources": ["https://example.com/feed.xml"],
        }

        fake_story = {
            "title": "Banco Central sinaliza nova discussão sobre juros",
            "link": "https://example.com/noticia-1",
            "summary": "Mercado acompanha os próximos passos da política monetária.",
            "published_at": "2026-06-16T08:00:00Z",
            "source_url": "https://example.com/feed.xml",
        }

        with patch.object(self.planner.research, "list_news_stories", return_value=[fake_story]):
            plan = self.planner.plan(job)

        self.assertEqual(plan["source"], "news")
        self.assertEqual(plan["topic"], fake_story["title"])
        self.assertIn("Mercado acompanha", plan["briefing"])

    def test_planner_skips_used_news_and_falls_back_to_scheduled(self) -> None:
        job = {
            "id": "yt-hybrid-repeat",
            "platform": "youtube",
            "topic_mode": "hybrid",
            "topics": ["economia", "selic"],
            "news_sources": ["https://example.com/feed.xml"],
        }

        repeated_story = {
            "title": "Economia acelera no trimestre",
            "link": "https://example.com/noticia-ja-usada",
            "summary": "Resumo",
            "published_at": "2026-06-16T08:00:00Z",
            "source_url": "https://example.com/feed.xml",
        }

        self.topic_history.mark_news_used(job["id"], repeated_story["link"])

        with patch.object(self.planner.research, "list_news_stories", return_value=[repeated_story]):
            plan = self.planner.plan(job)

        self.assertEqual(plan["source"], "scheduled")
        self.assertEqual(plan["topic"], "economia")

    def test_queue_count_created_for_job_on_date(self) -> None:
        self.queue.add_item(
            {
                "job_id": "job-1",
                "platform": "twitter",
                "account_id": "acc",
                "status": "ready",
                "created_at": "2026-06-16T08:00:00Z",
                "topic": "a",
            }
        )
        self.queue.add_item(
            {
                "job_id": "job-1",
                "platform": "twitter",
                "account_id": "acc",
                "status": "published",
                "created_at": "2026-06-16T12:00:00Z",
                "topic": "b",
            }
        )
        self.queue.add_item(
            {
                "job_id": "job-1",
                "platform": "twitter",
                "account_id": "acc",
                "status": "ready",
                "created_at": "2026-06-17T08:00:00Z",
                "topic": "c",
            }
        )

        count = self.queue.count_created_for_job_on("job-1", "twitter", "2026-06-16")
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
