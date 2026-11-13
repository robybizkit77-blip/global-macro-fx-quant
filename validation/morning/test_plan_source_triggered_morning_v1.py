"""Hermetic source-wake admission regressions for CET and CEST mornings."""
from datetime import datetime, timezone
import unittest
from zoneinfo import ZoneInfo
from validation.morning.plan_source_triggered_morning_v1 import decide

ROME = ZoneInfo("Europe/Rome")


def rome(day, h, minute):
    return datetime.fromisoformat(f"{day}T{h:02d}:{minute:02d}:00").replace(tzinfo=ROME)


def parent(**overrides):
    p = {"name": "Calendar News Operational Refresh V1",
         "event": "workflow_run", "head_branch": "main",
         "conclusion": "success", "updated_at": "2026-11-13T04:04:47Z"}
    return p | overrides


class SourceTriggeredMorningTest(unittest.TestCase):
    def test_actual_0504_calendar_event_can_wake_morning_before_0800(self):
        d = decide(rome("2026-11-13", 5, 6), "workflow_run", parent=parent())
        self.assertTrue(d["active"], d)
        self.assertEqual(d["edition"], "2026-11-13")
        self.assertEqual(d["reason"], "ADMITTED_SOURCE_EVENT_WAKEUP")

    def test_actual_0506_macro_chained_event_admitted(self):
        p = parent(name="Macro Persistent Daily V1",
                   updated_at="2026-11-13T04:06:39Z")
        self.assertTrue(decide(rome("2026-11-13", 5, 10),
                               "workflow_run", parent=p)["active"])

    def test_unrelated_failure_branch_or_fake_parent_rejected(self):
        for change in ({"name": "Unknown Writer"},
                       {"head_branch": "feature"},
                       {"conclusion": "failure"},
                       {"event": "pull_request"},
                       {"updated_at": "garbage"}):
            with self.subTest(change=change):
                d = decide(rome("2026-11-13", 5, 10),
                           "workflow_run", parent=parent(**change))
                self.assertFalse(d["active"], d)

    def test_no_backdated_or_future_source_completion(self):
        for updated in ("2026-11-12T23:45:00Z",
                        "2026-11-13T08:04:47Z",
                        "2026-11-13T04:59:00Z"):
            with self.subTest(updated=updated):
                # At 05:10 Rome, the source completion must not be in the future.
                self.assertFalse(decide(rome("2026-11-13", 5, 10),
                                 "workflow_run", parent=parent(updated_at=updated))["active"])

    def test_source_wakeup_after_deadline_never_retroactively_certified(self):
        d = decide(rome("2026-11-13", 8, 1),
                   "workflow_run", parent=parent())
        self.assertFalse(d["active"])
        self.assertEqual(d["reason"], "SOURCE_EVENT_OUTSIDE_PRE_0800_WINDOW")

    def test_weekend_rejected_even_if_source_succeeded(self):
        d = decide(rome("2026-11-14", 5, 10),
                   "workflow_run", parent=parent(updated_at="2026-11-14T04:05:00Z"))
        self.assertFalse(d["active"])

    def test_summer_dst_0504_clock_accepted(self):
        p = parent(updated_at="2026-07-08T03:04:00Z")
        d = decide(rome("2026-07-08", 5, 10), "workflow_run", parent=p)
        self.assertTrue(d["active"], d)

    def test_cet_and_cest_scheduled_twin(self):
        cet = rome("2026-11-13", 7, 11)
        cest = rome("2026-07-08", 7, 11)
        self.assertTrue(decide(cet, "schedule", "11 6 * * 1-5")["active"])
        self.assertFalse(decide(cet, "schedule", "11 5 * * 1-5")["active"])
        self.assertTrue(decide(cest, "schedule", "11 5 * * 1-5")["active"])
        self.assertFalse(decide(cest, "schedule", "11 6 * * 1-5")["active"])
        self.assertFalse(decide(cet, "schedule", "13 7 * * 1-5")["active"])

    def test_manual_recovery_keeps_legacy_morning_window(self):
        self.assertTrue(decide(rome("2026-11-13", 9, 12),
                               "workflow_dispatch")["active"])
        self.assertFalse(decide(rome("2026-11-13", 11, 1),
                                "workflow_dispatch")["active"])
        self.assertFalse(decide(rome("2026-11-13", 7, 4),
                                "push")["active"])


if __name__ == "__main__":
    unittest.main()
