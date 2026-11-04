"""Synthetic coverage states: qualified source must have BOTH saved cohorts."""
from __future__ import annotations

import copy
from datetime import datetime
from unittest.mock import patch
import unittest
from zoneinfo import ZoneInfo

from validation.forward import audit_daily_capture_coverage_v1 as guard
from validation.forward.test_frozen_core_prospective_capture_v11 import minimal

ROME = ZoneInfo("Europe/Rome")
TODAY = "2026-11-05"
CUT = "2026-11-05T19:35:00Z"


def source():
    fx, setup, core = minimal()
    fx["last_as_of"] = TODAY
    fx["rows"][-1]["Date"] = TODAY
    setup["price_asof"] = TODAY
    for key in ("as_of", "overlay_asof", "history_asof"):
        setup["price_audit"][key] = TODAY
    return fx, setup, core


class DailyCaptureCoverageTests(unittest.TestCase):
    def setUp(self):
        self.fx, self.pair, self.core = source()
        self.time = datetime(2026, 11, 5, 21, 17, tzinfo=ROME)
        self.qa = [{"local_date_rome": TODAY, "snapshot_id": "a"*64}]

    def audit(self, *, when=None, fx=None, pair=None, core_rows=None,
              qa_rows=None, cutoffs=None, quality_days=None):
        decisions = [] if core_rows is None else core_rows
        snapshots = self.qa if qa_rows is None else qa_rows
        with patch.object(guard, "inspect_core",
                          return_value={"cutoffs": [CUT] if cutoffs is None else cutoffs}), \
             patch.object(guard, "verify_journal",
                          return_value={TODAY} if quality_days is None else quality_days):
            return guard.audit(when or self.time, fx or self.fx, pair or self.pair,
                               self.core, decisions, snapshots)

    def test_positive_qualified_day_requires_both_durable_classes(self):
        r=self.audit()
        self.assertEqual(r["status"], "DAILY_CORE_AND_QUALITY_AWARE_DURABLE")
        self.assertTrue(r["certified_daily_capture"])
        self.assertFalse(r["blocks_workflow"])
        self.assertEqual(r["complete_core_28_pair_batches_today"], 1)
        self.assertEqual(r["verified_quality_aware_snapshots_today"], 1)
        self.assertFalse(r["does_not_validate_predictive_skill"] is False)
        self.assertFalse(r["original_v2_numeric_certified"])

    def test_source_present_but_no_core_is_hard_failure(self):
        r=self.audit(cutoffs=[])
        self.assertEqual(r["status"], "BLOCKED_CORE_28_PAIR_BATCH_MISSING_OR_DUPLICATED")
        self.assertTrue(r["blocks_workflow"])

    def test_source_present_but_no_quality_is_hard_failure(self):
        r=self.audit(qa_rows=[], quality_days=set())
        self.assertEqual(r["status"], "BLOCKED_QUALITY_AWARE_SNAPSHOT_MISSING_OR_DUPLICATED")
        self.assertTrue(r["blocks_workflow"])

    def test_duplicate_batch_or_quality_cannot_look_durable(self):
        self.assertTrue(self.audit(cutoffs=[CUT, CUT])["blocks_workflow"])
        self.assertTrue(self.audit(qa_rows=self.qa*2)["blocks_workflow"])

    def test_stale_ecb_cannot_claim_capture_or_assert_holiday(self):
        fx=copy.deepcopy(self.fx)
        fx["last_as_of"]="2026-11-04"
        r=self.audit(fx=fx)
        self.assertEqual(r["status"], "OFFICIAL_T0_NOT_CURRENT_REASON_UNDETERMINED")
        self.assertFalse(r["certified_daily_capture"])
        self.assertTrue(r["requires_source_review"])
        self.assertFalse(r["blocks_workflow"])

    def test_official_ecb_current_but_pair_setup_lags_is_hard_failure(self):
        setup=copy.deepcopy(self.pair)
        setup["price_asof"]="2026-11-04"
        r=self.audit(pair=setup)
        self.assertEqual(r["status"], "BLOCKED_PRICE_HANDOFF_OR_ADMISSION_CONTRACT")
        self.assertTrue(r["blocks_workflow"])

    def test_corrupt_current_official_quote_is_hard_failure(self):
        fx=copy.deepcopy(self.fx)
        fx["rows"][-1]["USD"]=None
        r=self.audit(fx=fx)
        self.assertEqual(r["status"], "BLOCKED_ECB_SOURCE_INTEGRITY")
        self.assertTrue(r["blocks_workflow"])

    def test_not_before_independent_window_nor_weekend(self):
        for timestamp in (datetime(2026,11,5,21,14,tzinfo=ROME),
                          datetime(2026,11,7,21,18,tzinfo=ROME)):
            r=self.audit(when=timestamp)
            self.assertEqual(r["status"], "OUTSIDE_2115_ROME_DAILY_ATTESTATION_WINDOW")
            self.assertFalse(r["certified_daily_capture"])

    def test_integrity_fail_closed_without_implicitly_recomputing_model(self):
        with patch.object(guard, "inspect_core", side_effect=ValueError("tampered")):
            r=guard.audit(self.time,self.fx,self.pair,self.core,[],self.qa)
        self.assertEqual(r["status"], "BLOCKED_FORWARD_JOURNAL_INTEGRITY")
        self.assertTrue(r["blocks_workflow"])
        self.assertFalse(r["core_recomputed"])
        self.assertFalse(r["quality_aware_new_signals"])

    def test_existing_2115_observer_is_single_cadence_and_gate_last(self):
        workflow=(guard.ROOT/".github/workflows/forward-ecb-reference-outcomes-v1.yml").read_text()
        self.assertEqual(workflow.count("cron: '15 19 * * 1-5'"),1)
        self.assertEqual(workflow.count("cron: '15 20 * * 1-5'"),1)
        self.assertIn("validation.forward.test_audit_daily_capture_coverage_v1",workflow)
        self.assertIn("validation.forward.audit_daily_capture_coverage_v1",workflow)
        self.assertIn("--enforce",workflow)
        self.assertLess(workflow.index("Commit only new non-executable ECB reference comparisons"),
                        workflow.index("Attest daily Core and Quality-Aware capture coverage"))


if __name__ == "__main__":
    unittest.main()
