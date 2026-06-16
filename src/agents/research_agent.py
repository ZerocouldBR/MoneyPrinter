from services.news_service import NewsService


class ResearchAgent:
    def __init__(self) -> None:
        self.news = NewsService()

    def list_news_stories(self, job: dict) -> list[dict]:
        sources = job.get("news_sources", [])
        if not isinstance(sources, list) or not sources:
            return []

        keywords = job.get("topics", [])
        blocked_terms = job.get("news_blacklist", [])
        max_age_hours = job.get("news_max_age_hours")
        scoring_weights = {
            "title_keyword_weight": job.get("news_title_keyword_weight"),
            "summary_keyword_weight": job.get("news_summary_keyword_weight"),
            "recency_weight": job.get("news_recency_weight"),
        }
        return self.news.fetch_entries(
            sources=sources,
            keywords=keywords,
            blocked_terms=blocked_terms,
            max_age_hours=max_age_hours,
            scoring_weights=scoring_weights,
        )

    def select_news_story(self, job: dict) -> dict | None:
        entries = self.list_news_stories(job)
        if not entries:
            return None

        return entries[0]

    def build_briefing(self, story: dict) -> str:
        title = str(story.get("title", "")).strip()
        summary = str(story.get("summary", "")).strip()
        source_url = str(story.get("source_url", "")).strip()

        parts = [part for part in [title, summary, source_url] if part]
        return " | ".join(parts)
