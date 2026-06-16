from agents.research_agent import ResearchAgent
from services.topic_history_service import TopicHistoryService


class PlannerAgent:
    def __init__(self) -> None:
        self.topic_history = TopicHistoryService()
        self.research = ResearchAgent()

    def plan(self, job: dict) -> dict:
        topic_mode = str(job.get("topic_mode", "scheduled")).strip().lower()

        if topic_mode == "news":
            news_plan = self._build_news_plan(job)
            if news_plan is not None:
                return news_plan
            return self._fallback_plan(job, topic_mode=topic_mode)

        if topic_mode == "hybrid":
            news_plan = self._build_news_plan(job)
            if news_plan is not None:
                return news_plan

            scheduled_plan = self._build_scheduled_plan(job, topic_mode=topic_mode)
            if scheduled_plan is not None:
                return scheduled_plan
            return self._fallback_plan(job, topic_mode=topic_mode)

        scheduled_plan = self._build_scheduled_plan(job, topic_mode=topic_mode)
        if scheduled_plan is not None:
            return scheduled_plan

        return self._fallback_plan(job, topic_mode=topic_mode)

    def _build_scheduled_plan(self, job: dict, topic_mode: str) -> dict | None:
        topics = job.get("topics", [])
        topic = self.topic_history.get_next_topic(job["id"], topics)
        if not topic:
            return None

        return {
            "topic": topic,
            "source": "scheduled",
            "topic_mode": topic_mode,
            "briefing": f"Scheduled topic selected for job {job['id']}: {topic}",
        }

    def _build_news_plan(self, job: dict) -> dict | None:
        for story in self.research.list_news_stories(job):
            story_link = str(story.get("link", "")).strip()
            if story_link and self.topic_history.was_news_used(job["id"], story_link):
                continue

            if story_link:
                self.topic_history.mark_news_used(job["id"], story_link)

            return {
                "topic": str(story.get("title", "")).strip(),
                "source": "news",
                "topic_mode": str(job.get("topic_mode", "news")).strip().lower(),
                "briefing": self.research.build_briefing(story),
                "source_url": story_link,
                "published_at": story.get("published_at"),
            }

        return None

    def _fallback_plan(self, job: dict, topic_mode: str) -> dict:
        fallback_topic = str(job.get("platform", "content")).strip().title()
        return {
            "topic": f"{fallback_topic} automation update",
            "source": "fallback",
            "topic_mode": topic_mode,
            "briefing": f"Fallback topic generated for platform {job.get('platform', 'content')}",
        }
