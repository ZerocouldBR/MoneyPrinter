from datetime import UTC
from datetime import datetime

from agents.monitor_agent import MonitorAgent
from cache import get_accounts
from classes.Tts import TTS
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from services.queue_service import QueueService
from status import success


class CreationAgent:
    def __init__(self) -> None:
        self.queue = QueueService()
        self.monitor = MonitorAgent()

    def create_for_job(self, job: dict, plan: dict) -> dict:
        run = self.monitor.start_run(
            "create_job",
            payload={"job_id": job["id"], "platform": job["platform"], "topic": plan["topic"]},
        )

        if job["platform"] == "youtube":
            created_item = self._create_youtube_item(job, plan)
            run.step("youtube_content_generated", payload={"video_path": created_item.get("video_path")})
        elif job["platform"] == "twitter":
            created_item = self._create_twitter_item(job, plan)
            run.step("twitter_content_generated", payload={"body_length": len(created_item.get("body") or "")})
        else:
            raise ValueError(f"Unsupported automation platform '{job['platform']}'.")

        run.finish("success", payload={"queue_item_id": created_item["id"]})
        success(f"Queued {job['platform']} item {created_item['id']} for job {job['id']}")
        return created_item

    def _find_account(self, provider: str, account_id: str) -> dict:
        for account in get_accounts(provider):
            if account.get("id") == account_id:
                return account
        raise ValueError(f"Account '{account_id}' not found for provider '{provider}'.")

    def _create_youtube_item(self, job: dict, plan: dict) -> dict:
        account = self._find_account("youtube", job["account_id"])
        youtube = YouTube(
            account["id"],
            account["nickname"],
            account["firefox_profile"],
            account["niche"],
            account["language"],
        )
        tts = TTS()
        video_path = youtube.generate_video(
            tts,
            topic=plan["topic"],
            context_brief=plan.get("briefing"),
        )

        return self.queue.add_item(
            {
                "job_id": job["id"],
                "platform": "youtube",
                "account_id": account["id"],
                "topic": plan["topic"],
                "source": plan["source"],
                "status": "ready",
                "created_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "video_path": video_path,
                "metadata": {
                    **getattr(youtube, "metadata", {}),
                    "planning": {
                        "source": plan.get("source"),
                        "briefing": plan.get("briefing"),
                        "source_url": plan.get("source_url"),
                        "published_at": plan.get("published_at"),
                    },
                },
            }
        )

    def _create_twitter_item(self, job: dict, plan: dict) -> dict:
        account = self._find_account("twitter", job["account_id"])
        twitter = Twitter(
            account["id"],
            account["nickname"],
            account["firefox_profile"],
            account["topic"],
        )
        body = twitter.generate_post(
            topic_override=plan["topic"],
            context_override=plan.get("briefing"),
        )

        return self.queue.add_item(
            {
                "job_id": job["id"],
                "platform": "twitter",
                "account_id": account["id"],
                "topic": plan["topic"],
                "source": plan["source"],
                "status": "ready",
                "created_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "body": body,
                "metadata": {
                    "topic": plan["topic"],
                    "planning": {
                        "source": plan.get("source"),
                        "briefing": plan.get("briefing"),
                        "source_url": plan.get("source_url"),
                        "published_at": plan.get("published_at"),
                    },
                },
            }
        )
