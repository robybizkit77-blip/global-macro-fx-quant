"""Hermetic safeguards for Morning Desk production recovery."""
from datetime import datetime, timezone
import unittest

from validation.orchestration.trigger_morning_editorial_recovery_v1 import decide


class MorningRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.clock = datetime(2026, 11, 11, 6, 40, tzinfo=timezone.utc)

    def run_info(self, status="completed", event="schedule", day="2026-11-11"):
        return {"created_at": day + "T06:11:00Z", "head_branch": "main",
                "event": event, "status": status}

    def test_missing_edition_dispatches(self):
        self.assertEqual(decide(self.clock, {"edition_date": "2026-11-10"},
                                [self.run_info()])["action"], "DISPATCH")

    def test_public_edition_is_only_canonical_proof(self):
        current = {"schema": "GMFQ_MORNING_MACRO_FX_V1", "edition_date": "2026-11-11",
                   "observation_cutoff_exclusive": "2026-11-11", "edition_status": "MORNING_SNAPSHOT"}
        self.assertEqual(decide(self.clock, current, [self.run_info()])["action"],
                         "SKIP_CURRENT_PUBLIC_EDITION")
        current["edition_status"] = "RECONSTRUCTION_NOT_POINT_IN_TIME"
        self.assertEqual(decide(self.clock, current, [self.run_info()])["action"], "DISPATCH")

    def test_pending_writer_never_double_dispatched(self):
        for status in ("queued", "in_progress", "waiting"):
            self.assertEqual(decide(self.clock, None, [self.run_info(status=status)])["action"],
                             "SKIP_EDITORIAL_WRITER_ACTIVE")

    def test_two_manual_attempts_are_terminal(self):
        runs = [self.run_info(event="workflow_dispatch") for _ in range(2)]
        self.assertEqual(decide(self.clock, None, runs)["action"], "BLOCK_RECOVERY_LIMIT")
        self.assertEqual(decide(self.clock, None, runs[:1])["action"], "DISPATCH")

    def test_clock_dst_and_weekend(self):
        for now in (datetime(2026, 11, 11, 5, 30, tzinfo=timezone.utc),
                    datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc),
                    datetime(2026, 11, 14, 7, 0, tzinfo=timezone.utc)):
            self.assertEqual(decide(now, None, [])["action"], "SKIP_OUTSIDE_MORNING_WINDOW")
        summer = datetime(2026, 7, 8, 5, 30, tzinfo=timezone.utc)
        self.assertEqual(decide(summer, None, [])["action"], "DISPATCH")

    def test_unrelated_branch_ignored(self):
        run = self.run_info(status="in_progress")
        run["head_branch"] = "feature"
        self.assertEqual(decide(self.clock, None, [run])["action"], "DISPATCH")


if __name__ == "__main__":
    unittest.main()
