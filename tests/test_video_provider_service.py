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

from services.video_provider_service import VideoProviderService


class VideoProviderServiceTests(unittest.TestCase):
    @patch("services.video_provider_service.get_video_generation_config")
    def test_none_provider_returns_no_video(self, config_mock) -> None:
        config_mock.return_value = {"provider": "none"}
        service = VideoProviderService()
        payload, provider = service.generate_video("prompt")
        self.assertIsNone(payload)
        self.assertEqual(provider, "none")

    @patch("services.video_provider_service.requests.get")
    @patch("services.video_provider_service.requests.post")
    @patch("services.video_provider_service.get_video_generation_config")
    def test_minimax_flow_downloads_video(self, config_mock, post_mock, get_mock) -> None:
        config_mock.return_value = {
            "provider": "minimax",
            "minimax_api_key": "secret",
            "minimax_base_url": "https://api.minimax.io/v1",
            "minimax_model": "MiniMax-Hailuo-2.3",
            "duration_seconds": 6,
            "resolution": "1080P",
            "poll_timeout_seconds": 30,
            "poll_interval_seconds": 1,
        }
        post_mock.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value={"task_id": "123"}))
        get_mock.side_effect = [
            Mock(raise_for_status=Mock(), json=Mock(return_value={"status": "Success", "file_id": "f-1"})),
            Mock(raise_for_status=Mock(), json=Mock(return_value={"file": {"download_url": "https://download/video.mp4"}})),
            Mock(raise_for_status=Mock(), content=b"video-bytes"),
        ]

        service = VideoProviderService()
        video_bytes, provider = service.generate_video("prompt")

        self.assertEqual(provider, "minimax")
        self.assertEqual(video_bytes, b"video-bytes")

    @patch("services.video_provider_service.requests.get")
    @patch("services.video_provider_service.requests.post")
    @patch("services.video_provider_service.get_video_generation_config")
    def test_gemini_flow_downloads_video(self, config_mock, post_mock, get_mock) -> None:
        config_mock.return_value = {
            "provider": "gemini",
            "gemini_api_key": "secret",
            "gemini_base_url": "https://generativelanguage.googleapis.com/v1beta",
            "gemini_model": "veo-3.1-generate-preview",
            "poll_timeout_seconds": 30,
            "poll_interval_seconds": 1,
        }
        post_mock.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value={"name": "operations/abc"}))
        get_mock.side_effect = [
            Mock(
                raise_for_status=Mock(),
                json=Mock(
                    return_value={
                        "done": True,
                        "response": {
                            "generateVideoResponse": {
                                "generatedSamples": [
                                    {"video": {"uri": "https://download/google-video.mp4"}}
                                ]
                            }
                        },
                    }
                ),
            ),
            Mock(raise_for_status=Mock(), content=b"google-video-bytes"),
        ]

        service = VideoProviderService()
        video_bytes, provider = service.generate_video("prompt")

        self.assertEqual(provider, "gemini-veo")
        self.assertEqual(video_bytes, b"google-video-bytes")


if __name__ == "__main__":
    unittest.main()
