import os
import sys
import types
import unittest
from unittest.mock import Mock
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

fake_srt_equalizer = types.ModuleType("srt_equalizer")
fake_srt_equalizer.equalize_srt_file = lambda *args, **kwargs: None
sys.modules.setdefault("srt_equalizer", fake_srt_equalizer)

from services.image_provider_service import ImageProviderService


class ImageProviderServiceTests(unittest.TestCase):
    @patch("services.image_provider_service.get_image_generation_config")
    def test_auto_provider_defaults_to_gemini(self, config_mock) -> None:
        config_mock.return_value = {
            "provider": "auto",
            "gemini_api_key": "key",
            "gemini_api_base_url": "https://example.com",
            "gemini_model": "model",
            "aspect_ratio": "9:16",
        }
        service = ImageProviderService()
        self.assertEqual(service.get_active_provider(), "gemini")

    @patch("services.image_provider_service.requests.post")
    @patch("services.image_provider_service.get_image_generation_config")
    def test_generate_with_gemini_returns_image_bytes(self, config_mock, post_mock) -> None:
        config_mock.return_value = {
            "provider": "gemini",
            "gemini_api_key": "key",
            "gemini_api_base_url": "https://example.com",
            "gemini_model": "model",
            "aspect_ratio": "9:16",
        }
        post_mock.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(
                return_value={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "inlineData": {
                                            "data": "aGVsbG8=",
                                            "mimeType": "image/png",
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ),
        )

        service = ImageProviderService()
        image_bytes, provider = service.generate_image("prompt")

        self.assertEqual(provider, "gemini")
        self.assertEqual(image_bytes, b"hello")


if __name__ == "__main__":
    unittest.main()
