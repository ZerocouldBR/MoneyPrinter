import os
import sys
import types
import unittest
from datetime import UTC
from datetime import datetime
from unittest.mock import Mock
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

fake_srt_equalizer = types.ModuleType("srt_equalizer")
fake_srt_equalizer.equalize_srt_file = lambda *args, **kwargs: None
sys.modules.setdefault("srt_equalizer", fake_srt_equalizer)

from services.news_service import NewsService


class NewsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = NewsService()

    @patch("services.news_service.requests.get")
    def test_fetch_entries_parses_rss_and_scores_keywords(self, get_mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <rss><channel>
          <item>
            <title>Selic pode mudar em breve</title>
            <link>https://example.com/1</link>
            <description>Economia e juros no radar do mercado.</description>
            <pubDate>Mon, 16 Jun 2026 08:00:00 GMT</pubDate>
          </item>
          <item>
            <title>Esportes do dia</title>
            <link>https://example.com/2</link>
            <description>Outro assunto.</description>
          </item>
        </channel></rss>
        """
        get_mock.return_value = response

        entries = self.service.fetch_entries(
            sources=["https://example.com/feed.xml"],
            keywords=["selic", "economia"],
        )

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Selic pode mudar em breve")
        self.assertEqual(entries[0]["link"], "https://example.com/1")
        self.assertTrue(entries[0]["score"] > entries[1]["score"])
        self.assertEqual(entries[0]["published_at"], "2026-06-16T08:00:00Z")

    @patch("services.news_service.requests.get")
    def test_fetch_entries_prefers_more_recent_story_when_relevance_is_similar(self, get_mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <rss><channel>
          <item>
            <title>Selic deve seguir no foco do mercado</title>
            <link>https://example.com/new</link>
            <description>Economia em destaque.</description>
            <pubDate>Mon, 16 Jun 2026 10:00:00 GMT</pubDate>
          </item>
          <item>
            <title>Selic deve seguir no foco do mercado</title>
            <link>https://example.com/old</link>
            <description>Economia em destaque.</description>
            <pubDate>Fri, 13 Jun 2026 10:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        get_mock.return_value = response

        with patch.object(self.service, "_utc_now", return_value=datetime(2026, 6, 16, 12, 0, tzinfo=UTC)):
            entries = self.service.fetch_entries(
                sources=["https://example.com/feed.xml"],
                keywords=["selic", "economia"],
            )

        self.assertEqual(entries[0]["link"], "https://example.com/new")
        self.assertTrue(entries[0]["score"] > entries[1]["score"])

    @patch("services.news_service.requests.get")
    def test_fetch_entries_filters_blocked_terms_and_old_stories(self, get_mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <rss><channel>
          <item>
            <title>Fofoca sobre celebridades</title>
            <link>https://example.com/blocked</link>
            <description>Assunto fora da pauta.</description>
            <pubDate>Mon, 16 Jun 2026 10:00:00 GMT</pubDate>
          </item>
          <item>
            <title>Economia com dado muito antigo</title>
            <link>https://example.com/old</link>
            <description>Resumo relevante.</description>
            <pubDate>Mon, 10 Jun 2026 10:00:00 GMT</pubDate>
          </item>
          <item>
            <title>Economia segue no radar</title>
            <link>https://example.com/valid</link>
            <description>Selic e mercado em destaque.</description>
            <pubDate>Mon, 16 Jun 2026 09:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        get_mock.return_value = response

        with patch.object(self.service, "_utc_now", return_value=datetime(2026, 6, 16, 12, 0, tzinfo=UTC)):
            entries = self.service.fetch_entries(
                sources=["https://example.com/feed.xml"],
                keywords=["economia", "selic"],
                blocked_terms=["fofoca", "celebridades"],
                max_age_hours=48,
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["link"], "https://example.com/valid")

    @patch("services.news_service.requests.get")
    def test_fetch_entries_allows_custom_scoring_weights(self, get_mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <rss><channel>
          <item>
            <title>Mercado hoje</title>
            <link>https://example.com/title-match</link>
            <description>Resumo genérico.</description>
            <pubDate>Mon, 16 Jun 2026 10:00:00 GMT</pubDate>
          </item>
          <item>
            <title>Panorama geral</title>
            <link>https://example.com/summary-match</link>
            <description>O mercado reage à selic e economia.</description>
            <pubDate>Mon, 16 Jun 2026 11:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        get_mock.return_value = response

        with patch.object(self.service, "_utc_now", return_value=datetime(2026, 6, 16, 12, 0, tzinfo=UTC)):
            entries = self.service.fetch_entries(
                sources=["https://example.com/feed.xml"],
                keywords=["mercado", "selic", "economia"],
                scoring_weights={
                    "title_keyword_weight": 1,
                    "summary_keyword_weight": 6,
                    "recency_weight": 0,
                },
            )

        self.assertEqual(entries[0]["link"], "https://example.com/summary-match")
        self.assertTrue(entries[0]["score"] > entries[1]["score"])

    @patch("services.news_service.requests.get")
    def test_fetch_entries_deduplicates_by_link(self, get_mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <rss><channel>
          <item>
            <title>Notícia 1</title>
            <link>https://example.com/dup</link>
            <description>Resumo 1</description>
          </item>
          <item>
            <title>Notícia 1 repetida</title>
            <link>https://example.com/dup</link>
            <description>Resumo 2</description>
          </item>
        </channel></rss>
        """
        get_mock.return_value = response

        entries = self.service.fetch_entries(sources=["https://example.com/feed.xml"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["link"], "https://example.com/dup")


if __name__ == "__main__":
    unittest.main()
