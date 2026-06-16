import json
import os
from datetime import UTC
from datetime import datetime
from typing import Optional

from config import ROOT_DIR


class MetricsService:
    def __init__(self) -> None:
        self.path = os.path.join(ROOT_DIR, ".mp", "runs.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def append_event(self, event: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def create_event(
        self,
        event_type: str,
        run_id: str,
        status: str,
        payload: Optional[dict] = None,
    ) -> dict:
        return {
            "event_type": event_type,
            "run_id": run_id,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "payload": payload or {},
        }
