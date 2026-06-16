import json
import os
from datetime import UTC
from datetime import datetime
from typing import Optional
from uuid import uuid4

from config import ROOT_DIR


class QueueService:
    def __init__(self) -> None:
        self.path = os.path.join(ROOT_DIR, ".mp", "content_queue.json")
        self._ensure_store()

    def _ensure_store(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump({"items": []}, file, indent=2)

    def _read(self) -> dict:
        self._ensure_store()
        with open(self.path, "r", encoding="utf-8") as file:
            parsed = json.load(file)

        if not isinstance(parsed, dict):
            return {"items": []}

        parsed.setdefault("items", [])
        return parsed

    def _write(self, payload: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    def list_items(
        self,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> list[dict]:
        items = self._read()["items"]
        filtered = []
        for item in items:
            if status and item.get("status") != status:
                continue
            if platform and item.get("platform") != platform:
                continue
            if job_id and item.get("job_id") != job_id:
                continue
            filtered.append(item)
        return filtered

    def add_item(self, item: dict) -> dict:
        payload = self._read()
        now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

        record = {
            "id": str(item.get("id") or uuid4()),
            "job_id": str(item.get("job_id", "")).strip(),
            "platform": str(item.get("platform", "")).strip().lower(),
            "account_id": str(item.get("account_id", "")).strip(),
            "topic": str(item.get("topic", "")).strip(),
            "source": str(item.get("source", "planned")).strip().lower(),
            "status": str(item.get("status", "planned")).strip().lower(),
            "created_at": str(item.get("created_at", now)),
            "scheduled_publish_at": item.get("scheduled_publish_at"),
            "video_path": item.get("video_path"),
            "body": item.get("body"),
            "metadata": item.get("metadata", {}),
            "error": item.get("error"),
            "published_at": item.get("published_at"),
        }

        payload["items"].append(record)
        self._write(payload)
        return record

    def get_item(self, item_id: str) -> Optional[dict]:
        for item in self._read()["items"]:
            if item.get("id") == item_id:
                return item
        return None

    def update_item(self, item_id: str, updates: dict) -> Optional[dict]:
        payload = self._read()
        updated = None

        for item in payload["items"]:
            if item.get("id") == item_id:
                item.update(updates)
                updated = item
                break

        if updated is not None:
            self._write(payload)

        return updated

    def count_created_for_job_on(self, job_id: str, platform: str, date_prefix: str) -> int:
        total = 0
        for item in self.list_items(platform=platform, job_id=job_id):
            created_at = str(item.get("created_at", ""))
            if created_at.startswith(date_prefix):
                total += 1
        return total

    def find_next_ready_item(self, platform: str, job_id: str) -> Optional[dict]:
        candidates = []
        for item in self.list_items(status="ready", platform=platform, job_id=job_id):
            sort_key = (
                item.get("scheduled_publish_at") or "9999-12-31T23:59:59",
                item.get("created_at") or "9999-12-31T23:59:59",
            )
            candidates.append((sort_key, item))

        if not candidates:
            return None

        candidates.sort(key=lambda pair: pair[0])
        return candidates[0][1]
