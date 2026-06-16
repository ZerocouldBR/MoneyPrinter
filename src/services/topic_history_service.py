import json
import os

from config import ROOT_DIR


class TopicHistoryService:
    def __init__(self) -> None:
        self.path = os.path.join(ROOT_DIR, ".mp", "topic_history.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump({"jobs": {}}, file, indent=2)

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as file:
            parsed = json.load(file)
        if not isinstance(parsed, dict):
            return {"jobs": {}}
        parsed.setdefault("jobs", {})
        return parsed

    def _write(self, payload: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    def get_next_topic(self, job_id: str, topics: list[str]) -> str | None:
        clean_topics = [topic.strip() for topic in topics if topic and topic.strip()]
        if not clean_topics:
            return None

        payload = self._read()
        job_state = payload["jobs"].setdefault(
            job_id,
            {"last_topic_index": -1, "used_news_links": []},
        )
        next_index = (int(job_state.get("last_topic_index", -1)) + 1) % len(clean_topics)
        job_state["last_topic_index"] = next_index
        self._write(payload)
        return clean_topics[next_index]

    def was_news_used(self, job_id: str, link: str) -> bool:
        payload = self._read()
        job_state = payload["jobs"].setdefault(
            job_id,
            {"last_topic_index": -1, "used_news_links": []},
        )
        clean_link = str(link or "").strip()
        return clean_link in job_state.get("used_news_links", [])

    def mark_news_used(self, job_id: str, link: str, max_links: int = 50) -> None:
        clean_link = str(link or "").strip()
        if not clean_link:
            return

        payload = self._read()
        job_state = payload["jobs"].setdefault(
            job_id,
            {"last_topic_index": -1, "used_news_links": []},
        )
        used_links = list(job_state.get("used_news_links", []))
        if clean_link in used_links:
            return

        used_links.append(clean_link)
        job_state["used_news_links"] = used_links[-max_links:]
        self._write(payload)
