"""Recovery can act only on an actual missing producer, with hard limits."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from validation.orchestration.trigger_early_morning_recovery_v1 import choose, ESSENTIAL

TZ = ZoneInfo("Europe/Rome")
def at(hour, minute):
    return dt.datetime(2026, 11, 10, hour, minute, tzinfo=TZ)
def run(id, event="schedule", status="completed", conclusion="success", time="05:00"):
    return {"id": id, "event": event, "head_branch": "main",
            "status": status, "conclusion": conclusion,
            "created_at": "2026-11-10T"+time+":00+01:00"}
def job(success=True):
    return [{"name": "orchestrate", "conclusion": "success",
             "steps": [{"name": n, "conclusion": "success" if success else "skipped"}
                       for n in ESSENTIAL]}]

class RecoveryTest(unittest.TestCase):
    def test_missing_source_triggers_prebrief(self):
        self.assertEqual(choose(at(5,22), [], {})["phase"], "prebrief")

    def test_0504_rome_source_event_can_recover_missed_prebrief(self):
        self.assertEqual(choose(at(5, 4), [], {})["action"], "DISPATCH")
        self.assertEqual(choose(at(5, 4), [], {})["phase"], "prebrief")
        self.assertEqual(choose(at(4, 59), [], {})["action"], "SKIP_OUTSIDE_RECOVERY_WINDOW")

    def test_pre_0515_retries_count_toward_same_two_attempt_limit(self):
        rr = [run(1, "workflow_dispatch", conclusion="failure", time="05:04"),
              run(2, "workflow_dispatch", conclusion="failure", time="05:20")]
        self.assertEqual(choose(at(6, 0), rr, {})["action"], "SKIP_RECOVERY_LIMIT_REACHED")

    def test_workflow_run_chain_source_can_trigger_safe_recovery(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[2] /
                    ".github/workflows/early-morning-recovery-v1.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event == 'workflow_run'", workflow)
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
    def test_missing_source_late_triggers_premorning(self):
        self.assertEqual(choose(at(7,0), [], {})["phase"], "premorning")
    def test_out_of_window_never_dispatches(self):
        for h in (4,8,10):
            self.assertNotEqual(choose(at(h,0), [], {})["action"], "DISPATCH")
    def test_green_skipped_cron_not_certified(self):
        self.assertEqual(choose(at(5,25), [run(1)], {1: job(False)})["action"], "DISPATCH")
    def test_actual_completed_morning_no_duplicate(self):
        self.assertEqual(choose(at(5,30), [run(1)], {1: job(True)})["action"],
                         "SKIP_ALREADY_VERIFIED_MORNING")
    def test_active_manual_no_duplicate(self):
        r = run(2, "workflow_dispatch", "in_progress", None, "05:20")
        self.assertEqual(choose(at(5,30), [r], {})["action"], "SKIP_PRODUCTION_ACTIVE")
    def test_active_schedule_with_real_job_no_duplicate(self):
        r = run(2, "schedule", "in_progress", None, "05:20")
        jobs = {2: [{"name": "orchestrate",
                     "steps": [{"name": ESSENTIAL[0], "status": "in_progress"}]}]}
        self.assertEqual(choose(at(5,30), [r], jobs)["action"], "SKIP_PRODUCTION_ACTIVE")
    def test_failed_schedule_can_recover(self):
        self.assertEqual(choose(at(6,0), [run(3, conclusion="failure")], {})["action"], "DISPATCH")
    def test_limit_manual_retries(self):
        rr = [run(1, "workflow_dispatch", conclusion="failure", time="05:18"),
              run(2, "workflow_dispatch", conclusion="failure", time="05:55")]
        self.assertEqual(choose(at(6,30), rr, {})["action"], "SKIP_RECOVERY_LIMIT_REACHED")
    def test_single_failed_manual_can_retry(self):
        rr = [run(1, "workflow_dispatch", conclusion="failure", time="05:19")]
        self.assertEqual(choose(at(6,20), rr, {})["action"], "DISPATCH")
    def test_previous_day_does_not_suppress_recovery(self):
        r = run(1)
        r["created_at"] = "2026-11-09T05:00:00+01:00"
        self.assertEqual(choose(at(5,30), [r], {1: job()})["action"], "DISPATCH")

if __name__ == "__main__":
    unittest.main()
