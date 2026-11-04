"""Isolated synthetic reference comparisons for Quality-Aware, never a real T0 backfill."""
from __future__ import annotations

import copy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import unittest

from validation.forward import capture_v2_quality_aware_prospective_v1 as qa
from validation.forward import observe_v2_quality_aware_ecb_reference_returns_v1 as obs
from validation.forward.test_capture_v2_quality_aware_prospective_v1 import (
    QualityAwareProspectiveCaptureTests as Fixture
)


class QualityAwareReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Fixture.setUpClass()
        cls.fixture = Fixture()
        cls.snap = cls.fixture.make()
        cls.cut = cls.fixture.cut
        cls.source = copy.deepcopy(cls.fixture.fx)
        cls.future_day = (cls.cut + timedelta(days=2)).date().isoformat()
        future = copy.deepcopy(cls.source["rows"][-1])
        future["Date"] = cls.future_day
        future["USD"] = round(float(future["USD"]) * 1.01, 8)
        cls.fx = copy.deepcopy(cls.source)
        cls.fx["rows"].append(future)
        cls.fx["last_as_of"] = cls.future_day
        cls.fx["row_count"] = len(cls.fx["rows"])

    def when(self, days):
        return self.cut + timedelta(days=days, hours=1)

    def test_maturity_exact_and_nonexecutability(self):
        before = obs.compute([self.snap], self.fx, self.when(0))
        self.assertEqual(before["new_matured_reference_rows"], 0)
        mature = obs.compute([self.snap], self.fx, self.when(2))
        self.assertEqual(mature["frozen_capture_dates"], 1)
        self.assertEqual(mature["new_matured_reference_rows"], 28)
        self.assertEqual(mature["waiting"]["new"], 28)
        self.assertTrue(mature["twenty_eight_pairs_are_not_independent_trials"])
        self.assertTrue(mature["no_H1_or_original_V2_model_claim"])
        self.assertEqual({x["horizon"] for x in mature["new_rows"]}, {"1D"})
        for row in mature["new_rows"]:
            self.assertEqual(row["quality_snapshot_id"], self.snap["snapshot_id"])
            self.assertEqual(row["first_observed_ecb_date_strictly_after_maturity"], self.future_day)
            self.assertFalse(row["quality_aware_signal_computed"])
            self.assertIsNone(row["trade_net_return"])
            self.assertIsNone(row["trade_direction"])
            self.assertIsNone(row["predictive_accuracy"])
            self.assertFalse(row["model_alpha_claim"])
            self.assertEqual(row["reference_return_sha256"],
                             qa.sha({k:v for k,v in row.items()
                                     if k != "reference_return_sha256"}))

    def test_idempotence_and_prior_tampering(self):
        first = obs.compute([self.snap], self.fx, self.when(2))
        repeated = obs.compute([self.snap], self.fx, self.when(2), first["new_rows"])
        self.assertEqual(repeated["new_matured_reference_rows"], 0)
        self.assertEqual(repeated["waiting"]["already_recorded"], 28)
        fake = copy.deepcopy(first["new_rows"])
        fake[0]["observed_reference_return_pct"] = 900.0
        with self.assertRaisesRegex(ValueError, "prior outcome seal"):
            obs.compute([self.snap], self.fx, self.when(2), fake)
        duplicated = first["new_rows"] + first["new_rows"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            obs.compute([self.snap], self.fx, self.when(2), duplicated)

    def test_no_future_leakage_and_t0_source_drift(self):
        with self.assertRaisesRegex(ValueError, "future"):
            obs.compute([self.snap], self.fx, self.cut-timedelta(hours=1))
        changed = copy.deepcopy(self.fx)
        for row in changed["rows"]:
            if row["Date"] == self.snap["official_ecb_t0_date"]:
                row["USD"] = float(row["USD"])*1.02
        with self.assertRaisesRegex(ValueError, "fixing changed"):
            obs.compute([self.snap], changed, self.when(2))

    def test_original_qa_journal_and_official_price_source_untouched(self):
        sources=[qa.JOURNAL, obs.FX_PATH]
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sources if p.is_file()}
        obs.compute([self.snap],self.fx,self.when(2))
        self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sources if p.is_file()})

    def test_workflow_uses_existing_schedule_and_qa_is_separate(self):
        workflow=(qa.ROOT/".github/workflows/forward-ecb-reference-outcomes-v1.yml").read_text()
        self.assertEqual(workflow.count("cron: '15 19 * * 1-5'"), 1)
        self.assertEqual(workflow.count("cron: '15 20 * * 1-5'"), 1)
        self.assertIn("observe_v2_quality_aware_ecb_reference_returns_v1", workflow)
        self.assertIn("V2_QUALITY_AWARE_ECB_REFERENCE_RETURNS_V1.jsonl", workflow)
        self.assertIn("QUALITY_AWARE_REFERENCE_OUTCOMES_NO_MODEL_CLAIM", workflow)
        self.assertIn("Verify V2 shadow observer separately", workflow)


if __name__ == "__main__":
    unittest.main()
