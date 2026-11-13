"""CFTC delayed holiday release catch-up gates, independent of live sources."""
from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from validation.orchestration.plan_cot_release_window_v1 import plan

ROME = ZoneInfo("Europe/Rome")


def when(iso):
    return datetime.fromisoformat(iso).replace(tzinfo=ROME)


class COTReleaseWindow(unittest.TestCase):
    def test_monday_16_nov_after_official_delay_is_admitted(self):
        report = plan(when("2026-11-16T22:20:00"), "schedule", "20 21 * * 1")
        self.assertTrue(report["should_run"], report)
        self.assertEqual(report["reason"], "MONDAY_CFTC_DELAY_RECOVERY")

    def test_next_thanksgiving_monday_same_recovery(self):
        self.assertTrue(plan(when("2026-11-30T22:20"), "schedule",
                             "20 21 * * 1")["should_run"])

    def test_summer_and_winter_twin_admission(self):
        cases = [
            ("2026-07-06T22:20", "20 20 * * 1", True),
            ("2026-07-06T22:20", "20 21 * * 1", False),
            ("2026-11-16T22:20", "20 21 * * 1", True),
            ("2026-11-16T22:20", "20 20 * * 1", False),
            ("2026-11-14T00:00", "0 23 * * 5", True),
            ("2026-11-14T00:00", "0 22 * * 5", False),
            ("2026-07-11T00:00", "0 22 * * 5", True),
            ("2026-07-11T00:00", "0 23 * * 5", False),
        ]
        for instant, slot, expected in cases:
            with self.subTest(instant=instant, slot=slot):
                self.assertEqual(plan(when(instant), "schedule", slot)["should_run"], expected)

    def test_early_monday_before_cftc_release_is_rejected(self):
        self.assertFalse(plan(when("2026-11-16T21:20"), "schedule",
                              "20 21 * * 1")["should_run"])
        self.assertFalse(plan(when("2026-11-16T18:00"), "schedule",
                              "20 21 * * 1")["should_run"])

    def test_delayed_github_event_into_tuesday_is_recoverable(self):
        self.assertTrue(plan(when("2026-11-17T04:10"), "schedule",
                             "20 21 * * 1")["should_run"])
        self.assertFalse(plan(when("2026-11-17T13:10"), "schedule",
                              "20 21 * * 1")["should_run"])

    def test_saturday_existing_retry_can_start_late_without_hour_exactness(self):
        self.assertTrue(plan(when("2026-11-14T03:39"), "schedule",
                             "0 23 * * 5")["should_run"])
        self.assertFalse(plan(when("2026-11-15T10:00"), "schedule",
                              "0 23 * * 5")["should_run"])

    def test_monday_slot_does_not_run_on_wrong_day_or_wrong_event(self):
        self.assertFalse(plan(when("2026-11-13T22:20"), "schedule",
                              "20 21 * * 1")["should_run"])
        self.assertFalse(plan(when("2026-11-16T22:20"), "workflow_run",
                              "20 21 * * 1")["should_run"])
        self.assertFalse(plan(when("2026-11-16T22:20"), "schedule",
                              "20 99 * * 1")["should_run"])

    def test_manual_and_pr_keep_existing_execution_contract(self):
        for event in ("push", "pull_request", "workflow_dispatch"):
            self.assertTrue(plan(when("2026-11-13T11:00"), event)["should_run"])

    def test_reject_naive_time(self):
        with self.assertRaises(ValueError):
            plan(datetime(2026, 11, 16, 22, 20), "schedule", "20 21 * * 1")


if __name__ == "__main__":
    unittest.main()
