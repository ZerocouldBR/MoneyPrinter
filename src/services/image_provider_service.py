import base64
import os
from typing import Optional

import requests

from config import get_image_generation_config
from status import error
from status import warning


class ImageProviderService:
    def __init__(self) -> None:
        self.config = get_image_generation_config()

    def get_active_provider(self) -> str:
        provider = str(self.config.get("provider", "gemini")).strip().lower()
        if provider in {"", "auto"}:
            return "gemini"
        return provider

    def generate_image(self, prompt: str) -> tuple[bytes | None, str]:
        provider = self.get_active_provider()
        if provider in {"gemini", "google", "nanobanana2"}:
            return self._generate_with_gemini(prompt), "gemini"
        if provider in {"fal", "falai", "haloui", "halo"}:
            warning(
                "Configured image provider requires custom integration details. "
                "Current build supports Gemini image generation directly and keeps the provider abstraction ready."
            )
            return None, provider
        warning(f"Unsupported image provider '{provider}'. Falling back to Gemini.")
        return self._generate_with_gemini(prompt), "gemini"

    def _generate_with_gemini(self, prompt: str) -> bytes | None:
        api_key = str(self.config.get("gemini_api_key", "")).strip()
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY", "").strip()

        if not api_key:
            error("Gemini image API key is not configured.")
            return None

        base_url = str(self.config.get("gemini_api_base_url", "")).rstrip("/")
        model = str(self.config.get("gemini_model", "")).strip()
        aspect_ratio = str(self.config.get("aspect_ratio", "9:16")).strip()

        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }

        response = requests.post(
            endpoint,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        body = response.json()

        candidates = body.get("candidates", [])
        for candidate in candidates:
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                inline_data = part.get("inlineData") or part.get("inline_data")
                if not inline_data:
                    continue
                data = inline_data.get("data")
                mime_type = inline_data.get("mimeType") or inline_data.get("mime_type", "")
                if data and str(mime_type).startswith("image/"):
                    return base64.b64decode(data)
        return None
