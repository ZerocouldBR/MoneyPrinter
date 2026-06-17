import time
from typing import Optional

import requests

from config import get_video_generation_config
from status import error
from status import warning


class VideoProviderService:
    def __init__(self) -> None:
        self.config = get_video_generation_config()

    def get_active_provider(self) -> str:
        provider = str(self.config.get("provider", "none")).strip().lower()
        if provider in {"", "auto", "none", "disabled"}:
            return "none"
        return provider

    def generate_video(self, prompt: str) -> tuple[bytes | None, str]:
        provider = self.get_active_provider()
        if provider == "none":
            return None, provider
        if provider in {"minimax", "hailuo", "haloui"}:
            return self._generate_with_minimax(prompt), "minimax"
        if provider in {"gemini", "veo", "google"}:
            return self._generate_with_gemini(prompt), "gemini-veo"
        warning(f"Unsupported video provider '{provider}'. Falling back to disabled mode.")
        return None, provider

    def _generate_with_minimax(self, prompt: str) -> bytes | None:
        api_key = str(self.config.get("minimax_api_key", "")).strip()
        if not api_key:
            error("MiniMax API key is not configured.")
            return None

        base_url = str(self.config.get("minimax_base_url", "https://api.minimax.io/v1")).rstrip("/")
        payload = {
            "model": str(self.config.get("minimax_model", "MiniMax-Hailuo-2.3")).strip(),
            "prompt": prompt,
            "duration": int(self.config.get("duration_seconds", 6)),
            "resolution": str(self.config.get("resolution", "1080P")).strip(),
        }

        response = requests.post(
            f"{base_url}/video_generation",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        body = response.json()
        task_id = body.get("task_id")
        if not task_id:
            warning(f"MiniMax did not return task_id. Response: {body}")
            return None

        status_payload = self._poll_minimax_status(base_url, api_key, task_id)
        file_id = status_payload.get("file_id")
        if not file_id:
            warning(f"MiniMax generation finished without file_id. Response: {status_payload}")
            return None

        download_response = requests.get(
            f"{base_url}/files/retrieve",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"file_id": file_id},
            timeout=120,
        )
        download_response.raise_for_status()
        download_payload = download_response.json()
        download_url = (
            download_payload.get("file", {}) or {}
        ).get("download_url") or download_payload.get("download_url")
        if not download_url:
            warning(f"MiniMax download URL was not found. Response: {download_payload}")
            return None

        binary_response = requests.get(download_url, timeout=300)
        binary_response.raise_for_status()
        return binary_response.content

    def _poll_minimax_status(self, base_url: str, api_key: str, task_id: str) -> dict:
        deadline = time.time() + int(self.config.get("poll_timeout_seconds", 900))
        interval = int(self.config.get("poll_interval_seconds", 10))

        while time.time() < deadline:
            response = requests.get(
                f"{base_url}/query/video_generation",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"task_id": task_id},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            status = str(payload.get("status", "")).strip().lower()
            if status in {"success", "succeeded", "completed"}:
                return payload
            if status in {"fail", "failed", "error"}:
                raise RuntimeError(f"MiniMax video generation failed: {payload}")
            time.sleep(interval)

        raise TimeoutError("MiniMax video generation timed out while polling task status.")

    def _generate_with_gemini(self, prompt: str) -> bytes | None:
        api_key = str(self.config.get("gemini_api_key", "")).strip()
        if not api_key:
            error("Gemini/Veo API key is not configured.")
            return None

        base_url = str(self.config.get("gemini_base_url", "https://generativelanguage.googleapis.com/v1beta")).rstrip("/")
        model = str(self.config.get("gemini_model", "veo-3.1-generate-preview")).strip()
        payload = {
            "instances": [{"prompt": prompt}],
        }

        response = requests.post(
            f"{base_url}/models/{model}:predictLongRunning",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        operation = response.json()
        operation_name = operation.get("name")
        if not operation_name:
            warning(f"Gemini/Veo did not return an operation name. Response: {operation}")
            return None

        status_payload = self._poll_gemini_operation(base_url, api_key, operation_name)
        video_uri = self._extract_gemini_video_uri(status_payload)
        if not video_uri:
            warning(f"Gemini/Veo did not return a downloadable video URI. Response: {status_payload}")
            return None

        binary_response = requests.get(
            video_uri,
            headers={"x-goog-api-key": api_key},
            timeout=300,
            allow_redirects=True,
        )
        binary_response.raise_for_status()
        return binary_response.content

    def _poll_gemini_operation(self, base_url: str, api_key: str, operation_name: str) -> dict:
        deadline = time.time() + int(self.config.get("poll_timeout_seconds", 900))
        interval = int(self.config.get("poll_interval_seconds", 10))

        while time.time() < deadline:
            response = requests.get(
                f"{base_url}/{operation_name}",
                headers={"x-goog-api-key": api_key},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            if bool(payload.get("done")):
                return payload
            time.sleep(interval)

        raise TimeoutError("Gemini/Veo video generation timed out while polling operation status.")

    def _extract_gemini_video_uri(self, payload: dict) -> Optional[str]:
        candidates = [
            (((payload.get("response") or {}).get("generateVideoResponse") or {}).get("generatedSamples") or []),
            (((payload.get("response") or {}).get("generated_videos") or [])),
            (((payload.get("response") or {}).get("generatedVideos") or [])),
        ]

        for candidate_list in candidates:
            for candidate in candidate_list:
                if not isinstance(candidate, dict):
                    continue
                video = candidate.get("video") or {}
                uri = video.get("uri") or candidate.get("uri")
                if uri:
                    return uri
        return None
