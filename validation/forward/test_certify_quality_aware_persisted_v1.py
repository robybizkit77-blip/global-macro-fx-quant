"""Independent future-only Quality-Aware durable proof, not a V2 signal."""
from __future__ import annotations
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from validation.forward.certify_quality_aware_persisted_v1 import audit
from validation.forward.test_capture_v2_quality_aware_prospective_v1 import (
    QualityAwareProspectiveCaptureTests as Synthetic,
)

ROME = ZoneInfo("Europe/Rome")


class IndependentDurabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Synthetic.setUpClass()
        cls.fixture = Synthetic()
        cls.snapshot = cls.fixture.make()
        cls.utc_now = cls.fixture.now.astimezone(ZoneInfo("UTC")) + timedelta(minutes=4)

    def run_audit(self, *, rows=None, time=None, admitted=True, persisted=True, existing=True):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "quality.jsonl"
            if existing:
                path.write_text("".join(json.dumps(x,sort_keys=True)+"\n"
                               for x in (rows if rows is not None else [self.snapshot])))
            return audit(now=time or self.utc_now, admitted=admitted,
                         core_persisted=persisted, path=path)

    def test_real_signed_24_28_synthetic_future_snapshot_could_be_certified(self):
        got = self.run_audit()
        self.assertEqual(got["status"], "QUALITY_AWARE_DURABLE_RESEARCH_COHORT_CERTIFIED")
        self.assertTrue(got["source_controlled_journal_verified"])
        self.assertTrue(got["quality_aware_cohort_certified"])
        self.assertEqual(got["economic_dimensions"], 24)
        self.assertEqual(got["fx_reference_pairs"], 28)
        self.assertFalse(got["original_V2_numeric_candidate_certified"])
        self.assertFalse(got["can_validate_H1_or_FX_predictive_skill"])
        self.assertTrue(got["original_V2_failure_not_masked"])

    def test_pre_registration_or_weekend_or_pre_19_never_claims(self):
        for t in [datetime(2026,11,1,20,30,tzinfo=ROME),
                  datetime(2026,11,2,18,59,tzinfo=ROME),
                  datetime(2026,11,7,20,30,tzinfo=ROME)]:
            with self.subTest(t=t):
                got=self.run_audit(time=t)
                self.assertEqual(got["status"],
                                 "OUTSIDE_FUTURE_QUALITY_AWARE_CUTOFF_NO_CLAIM")
                self.assertFalse(got["quality_aware_cohort_certified"])

    def test_blocked_source_admission_not_called_success(self):
        got=self.run_audit(admitted=False)
        self.assertEqual(got["status"],"NO_OFFICIAL_T0_ADMISSION_NO_CAPTURE_CLAIM")
        self.assertFalse(got["quality_aware_cohort_certified"])

    def test_primary_persistence_failure_cannot_look_green(self):
        got=self.run_audit(persisted=False)
        self.assertEqual(got["status"],
                         "BLOCKED_PRIMARY_CORE_PERSISTENCE_NOT_CERTIFIED")

    def test_absent_journal_is_not_a_captured_quality_snapshot(self):
        got=self.run_audit(existing=False)
        self.assertEqual(got["status"],"BLOCKED_QUALITY_AWARE_JOURNAL_NOT_IN_MAIN")

    def test_signed_but_stale_day_cannot_pass_current_day(self):
        future=self.utc_now+timedelta(days=1)
        while future.astimezone(ROME).weekday()>=5:
            future+=timedelta(days=1)
        got=self.run_audit(time=future)
        self.assertEqual(got["status"],"BLOCKED_QUALITY_AWARE_TODAY_NOT_DURABLE")

    def test_modified_snapshot_fails_integrity_without_resealing(self):
        damaged=copy.deepcopy(self.snapshot)
        damaged["strict_robust_z_missing_count"]+=1
        got=self.run_audit(rows=[damaged])
        self.assertEqual(got["status"],"BLOCKED_QUALITY_AWARE_JOURNAL_INTEGRITY")

    def test_duplicate_same_day_snapshot_is_not_idempotent_evidence(self):
        got=self.run_audit(rows=[self.snapshot,self.snapshot])
        self.assertEqual(got["status"],"BLOCKED_QUALITY_AWARE_JOURNAL_INTEGRITY")

    def test_malformed_jsonl_cannot_pass_as_empty_proof(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"broken.jsonl"
            path.write_text('{"incomplete":\n')
            got=audit(now=self.utc_now, admitted=True,
                      core_persisted=True, path=path)
        self.assertEqual(got["status"],"BLOCKED_QUALITY_AWARE_JOURNAL_INTEGRITY")

    def test_read_only_no_existing_real_quality_journal_modified(self):
        from validation.forward.capture_v2_quality_aware_prospective_v1 import JOURNAL
        before=JOURNAL.read_bytes() if JOURNAL.exists() else None
        self.run_audit()
        after=JOURNAL.read_bytes() if JOURNAL.exists() else None
        self.assertEqual(before,after)


if __name__ == "__main__":
    unittest.main()
