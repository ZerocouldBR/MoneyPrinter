import time
from datetime import UTC
from datetime import datetime
from uuid import uuid4

from services.metrics_service import MetricsService


class MonitoredRun:
    def __init__(self, metrics: MetricsService, run_type: str, payload: dict | None = None) -> None:
        self.metrics = metrics
        self.run_type = run_type
        self.payload = payload or {}
        self.run_id = str(uuid4())
        self.started_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        self._started_perf = time.perf_counter()
        self._step_started_perf = self._started_perf
        self.metrics.append_event(
            self.metrics.create_event(
                event_type=f"{self.run_type}_started",
                run_id=self.run_id,
                status="running",
                payload={**self.payload, "started_at": self.started_at},
            )
        )

    def step(self, step_name: str, payload: dict | None = None) -> None:
        now_perf = time.perf_counter()
        elapsed = round(now_perf - self._step_started_perf, 3)
        self._step_started_perf = now_perf
        self.metrics.append_event(
            self.metrics.create_event(
                event_type=f"{self.run_type}_step",
                run_id=self.run_id,
                status="ok",
                payload={"step": step_name, "elapsed_seconds": elapsed, **(payload or {})},
            )
        )

    def finish(self, status: str, payload: dict | None = None) -> None:
        total_elapsed = round(time.perf_counter() - self._started_perf, 3)
        self.metrics.append_event(
            self.metrics.create_event(
                event_type=f"{self.run_type}_finished",
                run_id=self.run_id,
                status=status,
                payload={"total_elapsed_seconds": total_elapsed, **(payload or {})},
            )
        )


class MonitorAgent:
    def __init__(self) -> None:
        self.metrics = MetricsService()

    def start_run(self, run_type: str, payload: dict | None = None) -> MonitoredRun:
        return MonitoredRun(self.metrics, run_type=run_type, payload=payload)
