from datetime import UTC
from datetime import datetime

from agents.monitor_agent import MonitorAgent
from cache import get_accounts
from classes.Twitter import Twitter
from classes.YouTube import YouTube
from post_bridge_integration import maybe_crosspost_youtube_short
from services.queue_service import QueueService
from status import success
from status import warning


class PublisherAgent:
    def __init__(self) -> None:
        self.queue = QueueService()
        self.monitor = MonitorAgent()

    def publish_next_for_job(self, job: dict) -> dict | None:
        item = self.queue.find_next_ready_item(platform=job["platform"], job_id=job["id"])
        if item is None:
            warning(f"No ready queue items found for job {job['id']}.")
            return None

        return self._publish_item_for_job(job, item)

    def publish_item_by_id(self, item_id: str) -> dict:
        item = self.queue.get_item(item_id)
        if item is None:
            raise ValueError(f"Queue item '{item_id}' was not found.")

        job = {
            "id": item.get("job_id", "manual"),
            "platform": item.get("platform", ""),
            "account_id": item.get("account_id", ""),
        }
        return self._publish_item_for_job(job, item)

    def _publish_item_for_job(self, job: dict, item: dict) -> dict:
        run = self.monitor.start_run(
            "publish_job",
            payload={"job_id": job["id"], "platform": job["platform"], "queue_item_id": item["id"]},
        )

        self.queue.update_item(item["id"], {"status": "publishing", "error": None})

        try:
            if job["platform"] == "youtube":
                self._publish_youtube_item(item)
                run.step("youtube_published", payload={"video_path": item.get("video_path")})
            elif job["platform"] == "twitter":
                self._publish_twitter_item(item)
                run.step("twitter_published", payload={"body_length": len(item.get("body") or "")})
            else:
                raise ValueError(f"Unsupported automation platform '{job['platform']}'.")

            published_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
            updated = self.queue.update_item(
                item["id"],
                {"status": "published", "published_at": published_at},
            )
            run.finish("success", payload={"published_at": published_at})
            success(f"Published queue item {item['id']} for job {job['id']}")
            return updated
        except Exception as exc:
            self.queue.update_item(
                item["id"],
                {"status": "failed", "error": str(exc)},
            )
            run.finish("failed", payload={"error": str(exc)})
            raise

    def _find_account(self, provider: str, account_id: str) -> dict:
        for account in get_accounts(provider):
            if account.get("id") == account_id:
                return account
        raise ValueError(f"Account '{account_id}' not found for provider '{provider}'.")

    def _publish_youtube_item(self, item: dict) -> None:
        account = self._find_account("youtube", item["account_id"])
        youtube = YouTube(
            account["id"],
            account["nickname"],
            account["firefox_profile"],
            account["niche"],
            account["language"],
        )
        youtube.metadata = item.get("metadata", {})
        youtube.video_path = item.get("video_path")

        upload_success = youtube.upload_video()
        if not upload_success:
            raise RuntimeError("YouTube upload failed.")

        maybe_crosspost_youtube_short(
            video_path=youtube.video_path,
            title=youtube.metadata.get("title", ""),
            interactive=False,
        )

    def _publish_twitter_item(self, item: dict) -> None:
        account = self._find_account("twitter", item["account_id"])
        twitter = Twitter(
            account["id"],
            account["nickname"],
            account["firefox_profile"],
            account["topic"],
        )
        body = str(item.get("body", "")).strip()
        if not body:
            raise ValueError("Twitter queue item body is empty.")
        twitter.post(body)
