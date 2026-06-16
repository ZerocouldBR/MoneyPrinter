from agents.creation_agent import CreationAgent
from agents.planner_agent import PlannerAgent
from agents.publisher_agent import PublisherAgent
from config import get_automation_config
from services.queue_service import QueueService
from services.schedule_service import ScheduleService
from status import info
from status import success
from status import warning


class SchedulerAgent:
    def __init__(self) -> None:
        self.schedule = ScheduleService()
        self.queue = QueueService()
        self.planner = PlannerAgent()
        self.creator = CreationAgent()
        self.publisher = PublisherAgent()

    def run_once(self) -> dict:
        config = get_automation_config()
        if not config["enabled"]:
            warning("Automation scheduler is disabled in config.json.")
            return {"created": 0, "published": 0}

        now = self.schedule.get_now(config["timezone"])
        summary = {"created": 0, "published": 0}

        for job in config["jobs"]:
            if not job["enabled"]:
                continue

            try:
                self._run_create_if_due(job, now, summary)
            except Exception as exc:
                warning(f"Create flow failed for job {job['id']}: {exc}")

            try:
                self._run_publish_if_due(job, now, summary)
            except Exception as exc:
                warning(f"Publish flow failed for job {job['id']}: {exc}")

        success(
            f"Scheduler cycle finished. Created: {summary['created']} | Published: {summary['published']}"
        )
        return summary

    def _run_create_if_due(self, job: dict, now, summary: dict) -> None:
        cron_expression = job.get("create_cron", "")
        if not cron_expression:
            return
        if not self.schedule.is_due(cron_expression, now):
            return
        if self.schedule.was_already_executed(job["id"], "create", now):
            info(f"Skipping duplicate create execution for job {job['id']}")
            return

        created_today = self.queue.count_created_for_job_on(
            job_id=job["id"],
            platform=job["platform"],
            date_prefix=now.date().isoformat(),
        )
        if created_today >= int(job.get("max_per_day", 1)):
            warning(f"Skipping create for job {job['id']} because max_per_day was reached.")
            self.schedule.mark_executed(job["id"], "create", now)
            return

        plan = self.planner.plan(job)
        self.creator.create_for_job(job, plan)
        self.schedule.mark_executed(job["id"], "create", now)
        summary["created"] += 1

    def _run_publish_if_due(self, job: dict, now, summary: dict) -> None:
        cron_expression = job.get("publish_cron", "")
        if not cron_expression:
            return
        if not self.schedule.is_due(cron_expression, now):
            return
        if self.schedule.was_already_executed(job["id"], "publish", now):
            info(f"Skipping duplicate publish execution for job {job['id']}")
            return

        published = self.publisher.publish_next_for_job(job)
        self.schedule.mark_executed(job["id"], "publish", now)
        if published is not None:
            summary["published"] += 1
