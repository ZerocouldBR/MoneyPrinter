import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

fake_srt_equalizer = types.ModuleType("srt_equalizer")
fake_srt_equalizer.equalize_srt_file = lambda *args, **kwargs: None
sys.modules.setdefault("srt_equalizer", fake_srt_equalizer)

from utils import rem_temp_files


class PreserveOutputsTests(unittest.TestCase):
    def test_rem_temp_files_keeps_generated_media_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mp_dir = os.path.join(temp_dir, ".mp")
            os.makedirs(mp_dir, exist_ok=True)

            mp4_path = os.path.join(mp_dir, "video.mp4")
            png_path = os.path.join(mp_dir, "image.png")
            wav_path = os.path.join(mp_dir, "audio.wav")
            json_path = os.path.join(mp_dir, "state.json")
            temp_path = os.path.join(mp_dir, "TEMP_MPY_test.tmp")

            for path in [mp4_path, png_path, wav_path, json_path, temp_path]:
                with open(path, "wb") as file:
                    file.write(b"data")

            with patch("utils.ROOT_DIR", temp_dir):
                rem_temp_files()

            self.assertTrue(os.path.exists(mp4_path))
            self.assertTrue(os.path.exists(png_path))
            self.assertTrue(os.path.exists(wav_path))
            self.assertTrue(os.path.exists(json_path))
            self.assertFalse(os.path.exists(temp_path))


if __name__ == "__main__":
    unittest.main()
