import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from config import ROOT_DIR


class ScheduleService:
    def __init__(self) -> None:
        self.path = os.path.join(ROOT_DIR, ".mp", "scheduler_state.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump({"executions": {}}, file, indent=2)

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as file:
            parsed = json.load(file)
        if not isinstance(parsed, dict):
            return {"executions": {}}
        parsed.setdefault("executions", {})
        return parsed

    def _write(self, payload: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    def get_now(self, timezone_name: str) -> datetime:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except Exception:
            return datetime.now()

    def is_due(self, cron_expression: str, current_time: datetime) -> bool:
        cron_expression = str(cron_expression or "").strip()
        if not cron_expression:
            return False

        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{cron_expression}'. Expected 5 fields."
            )

        minute, hour, day, month, weekday = parts
        values = [
            (minute, current_time.minute, 0, 59),
            (hour, current_time.hour, 0, 23),
            (day, current_time.day, 1, 31),
            (month, current_time.month, 1, 12),
            (weekday, (current_time.weekday() + 1) % 7, 0, 6),
        ]
        return all(self._field_matches(field, value, min_value, max_value) for field, value, min_value, max_value in values)

    def _field_matches(self, field: str, value: int, min_value: int, max_value: int) -> bool:
        field = field.strip()
        if field == "*":
            return True

        for token in field.split(","):
            token = token.strip()
            if not token:
                continue
            if self._token_matches(token, value, min_value, max_value):
                return True
        return False

    def _token_matches(self, token: str, value: int, min_value: int, max_value: int) -> bool:
        if token == "*":
            return True

        base = token
        step = 1
        if "/" in token:
            base, step_str = token.split("/", 1)
            step = int(step_str)
            if step <= 0:
                return False

        allowed_values = []
        if base in {"", "*"}:
            allowed_values = list(range(min_value, max_value + 1))
        elif "-" in base:
            start_str, end_str = base.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            if end < start:
                return False
            allowed_values = list(range(start, end + 1))
        else:
            try:
                return int(base) == value
            except ValueError:
                return False

        if step > 1:
            allowed_values = [candidate for index, candidate in enumerate(allowed_values) if index % step == 0]

        return value in allowed_values

    def was_already_executed(self, job_id: str, action: str, current_time: datetime) -> bool:
        payload = self._read()
        key = f"{job_id}:{action}"
        last_stamp = payload["executions"].get(key)
        current_stamp = current_time.strftime("%Y-%m-%dT%H:%M")
        return last_stamp == current_stamp

    def mark_executed(self, job_id: str, action: str, current_time: datetime) -> None:
        payload = self._read()
        key = f"{job_id}:{action}"
        payload["executions"][key] = current_time.strftime("%Y-%m-%dT%H:%M")
        self._write(payload)
