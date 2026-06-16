import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

fake_srt_equalizer = types.ModuleType("srt_equalizer")
fake_srt_equalizer.equalize_srt_file = lambda *args, **kwargs: None
sys.modules.setdefault("srt_equalizer", fake_srt_equalizer)

from services.schedule_service import ScheduleService


class ScheduleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        patcher = patch("services.schedule_service.ROOT_DIR", self.tempdir.name)
        self.addCleanup(patcher.stop)
        patcher.start()
        self.service = ScheduleService()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_cron_matches_expected_minute(self) -> None:
        current = datetime(2026, 6, 16, 2, 0)
        self.assertTrue(self.service.is_due("0 2 * * *", current))
        self.assertFalse(self.service.is_due("30 8 * * *", current))

    def test_cron_supports_step_values(self) -> None:
        current = datetime(2026, 6, 16, 8, 30)
        self.assertTrue(self.service.is_due("*/15 8 * * *", current))
        self.assertFalse(self.service.is_due("*/20 8 * * *", current))

    def test_execution_state_blocks_duplicate_run_in_same_minute(self) -> None:
        current = datetime(2026, 6, 16, 8, 30)
        self.assertFalse(self.service.was_already_executed("job-1", "create", current))
        self.service.mark_executed("job-1", "create", current)
        self.assertTrue(self.service.was_already_executed("job-1", "create", current))


if __name__ == "__main__":
    unittest.main()
