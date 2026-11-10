"""Regression tests: a green CI run must never impersonate 08:00 delivery."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from validation.orchestration.check_independent_morning_0800_v1 import (
    PATHS, REQUIRED_STEPS, eligible, evaluate, schedule_applies,
)

ROME = ZoneInfo("Europe/Rome")
READY = {"operational_state": "DAILY_READY_WITH_DOCUMENTED_GAPS",
         "critical_daily_problems": [],
         "expected_previous_weekday": "2026-11-09"}


def fake(run_id, when, conclusion="success"):
    return {"id": run_id, "name": "Daily Data Orchestrator V2",
            "event": "schedule", "head_branch": "main",
            "created_at": when, "status": "completed", "conclusion": conclusion}


def proof(finished="2026-11-10T07:57:00+01:00", steps=None, conclusion="success"):
    return [{"name": "orchestrate", "conclusion": conclusion, "completed_at": finished,
             "steps": [{"name": name, "conclusion": (steps or {}).get(name, "success")}
                       for name in REQUIRED_STEPS]}]


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 10, 8, 12, tzinfo=ROME)
        self.runs = [
            fake(100, "2026-11-10T04:48:00+01:00"),
            fake(101, "2026-11-10T07:47:00+01:00"),
        ]
        self.jobs = {100: proof("2026-11-10T05:30:00+01:00"),
                     101: proof()}
        self.parity = {p: True for p in PATHS}
        self.public = {p: True for p in PATHS}

    def audit(self, **kwargs):
        data = dict(now=self.now, runs=self.runs, jobs=self.jobs,
                    readiness=READY, parity=self.parity, public=self.public)
        data.update(kwargs)
        return evaluate(**data)

    def test_healthy_full_morning_with_public_proof_passes(self):
        self.assertEqual(self.audit()["status"], "PASS_INDEPENDENT_0800_PROOF")
        self.assertEqual(self.audit()["on_time_certified_run_ids"], [100, 101])

    def test_prebrief_genuinely_completed_even_when_0745_schedule_missing(self):
        out = self.audit(runs=self.runs[:1])
        self.assertEqual(out["status"], "PASS_INDEPENDENT_0800_PROOF")
        self.assertEqual(out["on_time_certified_run_ids"], [100])

    def test_late_run_cannot_impersonate_on_time(self):
        late = fake(101, "2026-11-10T08:10:00+01:00")
        out = self.audit(runs=[late], jobs={101: proof("2026-11-10T08:11:00+01:00")})
        self.assertIn("NO_COMPLETED_SUCCESSFUL_MORNING_SLA_BY_0800", out["problems"])

    def test_recovered_manual_full_pipeline_is_eligible(self):
        rescue = {**self.runs[0], "event": "workflow_dispatch"}
        out = self.audit(runs=[rescue], jobs={100: self.jobs[100]})
        self.assertEqual(out["status"], "PASS_INDEPENDENT_0800_PROOF")
        self.assertEqual(out["recovery_run_ids_today"], [100])

    def test_green_workflow_with_skipped_audit_step_is_not_proof(self):
        broken = {100: proof(steps={REQUIRED_STEPS[2]: "skipped"}),
                  101: proof(steps={REQUIRED_STEPS[2]: "skipped"})}
        out = self.audit(jobs=broken)
        self.assertIn("NO_COMPLETED_SUCCESSFUL_MORNING_SLA_BY_0800",
                      out["problems"])

    def test_successful_job_that_finishes_after_deadline_is_not_proof(self):
        jobs = {100: proof("2026-11-10T08:01:00+01:00"),
                101: proof("2026-11-10T08:03:00+01:00")}
        out = self.audit(jobs=jobs)
        self.assertEqual(out["on_time_certified_run_ids"], [])

    def test_live_feed_staleness_fails(self):
        readiness = {**READY, "critical_daily_problems": ["PAIR_PRICE"]}
        self.assertIn("LATEST_MAIN_DAILY_SOURCES_NOT_READY",
                      self.audit(readiness=readiness)["problems"])

    def test_public_cdn_stale_even_when_git_parity_passes(self):
        public = {**self.public, PATHS[2]: False}
        self.assertIn("PUBLIC_HTTP_MISMATCH:" + PATHS[2],
                      self.audit(public=public)["problems"])

    def test_pages_branch_stale_even_when_public_bytes_match(self):
        parity = {**self.parity, PATHS[0]: False}
        self.assertIn("MAIN_GH_PAGES_MISMATCH:" + PATHS[0],
                      self.audit(parity=parity)["problems"])

    def test_non_production_branch_run_does_not_certify(self):
        runs = [{**r, "head_branch": "feature"} for r in self.runs]
        self.assertEqual(self.audit(runs=runs)["on_time_certified_run_ids"], [])

    def test_does_not_certify_before_eight(self):
        now = dt.datetime(2026, 11, 10, 7, 59, tzinfo=ROME)
        out = self.audit(now=now)
        self.assertIn("AUDIT_BEFORE_0800_CANNOT_CERTIFY", out["problems"])

    def test_cet_and_cest_crons_only_on_correct_offset(self):
        cet = dt.datetime(2026, 11, 10, 8, 8, tzinfo=ROME)
        cest = dt.datetime(2026, 7, 10, 8, 8, tzinfo=ROME)
        self.assertTrue(schedule_applies("08 7 * * 1-5", cet))
        self.assertFalse(schedule_applies("08 6 * * 1-5", cet))
        self.assertTrue(schedule_applies("08 6 * * 1-5", cest))
        self.assertFalse(schedule_applies("08 7 * * 1-5", cest))

    def test_run_with_no_real_job_steps_never_passes(self):
        self.assertFalse(eligible(self.runs[0],
                                  [{"name": "orchestrate",
                                    "conclusion": "success",
                                    "completed_at": "2026-11-10T05:30:00+01:00",
                                    "steps": []}],
                                  dt.datetime(2026, 11, 10, 8, tzinfo=ROME)))


if __name__ == "__main__":
    unittest.main()
