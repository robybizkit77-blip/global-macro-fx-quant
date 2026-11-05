#!/usr/bin/env python3
"""Status reporting must never claim alpha from pre-registered test fixtures."""
import copy
from datetime import datetime
import json
import unittest
from zoneinfo import ZoneInfo

from validation.quant.test_fxv2_6m_prospective_trial_v1 import fixture,at
from validation.quant.fxv2_6m_prospective_trial_v1 import freeze,observe
from validation.quant.fxv2_6m_prospective_status_v1 import build,SCHEMA


class ResearchStatusTests(unittest.TestCase):
    def test_real_pre_registration_is_explicitly_zero(self):
        policy,fx,quotes,macro=fixture()
        # Before registration, use the REAL available ECB archive; synthetic
        # Nov 6 test fixtures must not leak into a Nov 5 status report.
        from validation.quant.fxv2_6m_prospective_trial_v1 import FX_PATH
        fx=json.loads(FX_PATH.read_text())
        report=build(policy,fx,macro,[],[],at("2026-11-05T15:00:00"))
        self.assertEqual(report["schema"],SCHEMA)
        self.assertEqual(report["report_status"],
            "PREREGISTERED_BEFORE_FIRST_ELIGIBLE_CAPTURE")
        self.assertEqual(report["summary"]["pair_universe"],28)
        self.assertEqual(report["summary"]["actual_prospective_capture_days"],0)
        self.assertEqual(report["summary"]["experimental_direction_observations"],0)
        self.assertEqual(report["summary"]["outcomes_observed_after_5_future_fixings"],0)
        self.assertEqual(report["summary"]["matured_outcomes_not_recorded"],0)
        self.assertFalse(report["eligible_for_predictive_claim"])
        self.assertFalse(report["predictive_skill_validated"])
        self.assertIsNone(report["sharpe"])
        self.assertIsNone(report["alpha"])
        self.assertTrue(all(r["last_capture_state"]=="NOT_YET_OBSERVED"
            for r in report["pairs"].values()))

    def test_freeze_not_to_be_confused_with_matured_outcome(self):
        policy,fx,quotes,macro=fixture()
        doc,_=freeze(at("2026-11-06T20:30:00"),policy,fx,quotes,macro,[])
        report=build(policy,fx,macro,[doc],[],at("2026-11-06T20:35:00"))
        self.assertEqual(report["report_status"],
            "PROSPECTIVE_COLLECTION_IN_PROGRESS_NOT_VALIDATED")
        self.assertEqual(report["summary"]["actual_prospective_capture_days"],1)
        self.assertEqual(report["summary"]["frozen_28_pair_rows"],28)
        self.assertEqual(report["summary"]["experimental_direction_observations"],
                         doc["new_experimental_directions"])
        self.assertEqual(report["summary"]["outcomes_observed_after_5_future_fixings"],0)
        self.assertEqual(report["summary"]["frozen_directions_awaiting_maturity"],
                         doc["new_experimental_directions"])
        self.assertEqual(report["pairs"]["USD/CHF"]["last_capture_state"],
                         "FROZEN_EXPERIMENTAL_DIRECTION")
        self.assertEqual(report["pairs"]["AUD/CAD"]["last_capture_state"],
                         "ABSTAIN_NO_SUPPORTED_6M_SOURCE")
        self.assertFalse(report["inference_review_threshold_reached"])

    def test_missing_matured_outcome_explicitly_flags_attention(self):
        policy,fx,quotes,macro=fixture()
        doc,_=freeze(at("2026-11-06T20:00:00"),policy,fx,quotes,macro,[])
        future=copy.deepcopy(fx)
        for d in ("2026-11-09","2026-11-10","2026-11-11",
                  "2026-11-12","2026-11-13"):
            last=future["rows"][-1]
            future["rows"].append({**last,"Date":d,"USD":last["USD"]*1.002})
        future["last_as_of"]="2026-11-13"
        future["row_count"]=len(future["rows"])
        empty=build(policy,future,macro,[doc],[],at("2026-11-13T20:30:00"))
        self.assertEqual(empty["report_status"],
                         "MATURED_OUTCOMES_NOT_YET_RECORDED_ATTENTION")
        self.assertGreater(empty["summary"]["matured_outcomes_not_recorded"],0)
        outcomes=observe(at("2026-11-13T20:30:00"),
                         policy,future,[doc],[])
        full=build(policy,future,macro,[doc],outcomes,at("2026-11-13T20:40:00"))
        self.assertEqual(full["summary"]["outcomes_observed_after_5_future_fixings"],
                         doc["new_experimental_directions"])
        self.assertEqual(full["summary"]["matured_outcomes_not_recorded"],0)
        self.assertFalse(full["eligible_for_predictive_claim"])
        self.assertEqual(full["report_status"],
                         "PROSPECTIVE_COLLECTION_IN_PROGRESS_NOT_VALIDATED")

    def test_outcome_source_must_reference_original_frozen_hash_and_maturity(self):
        policy,fx,quotes,macro=fixture()
        doc,_=freeze(at("2026-11-06T20:00:00"),policy,fx,quotes,macro,[])
        future=copy.deepcopy(fx)
        for d in ("2026-11-09","2026-11-10","2026-11-11",
                  "2026-11-12","2026-11-13"):
            future["rows"].append({**future["rows"][-1],"Date":d})
        future["last_as_of"]="2026-11-13"
        future["row_count"]=len(future["rows"])
        outcomes=observe(at("2026-11-13T20:15:00"),
                         policy,future,[doc],[])
        from validation.quant.fxv2_6m_prospective_trial_v1 import seal
        corrupt=copy.deepcopy(outcomes)
        corrupt[0]["original_freeze_sha256"]="f"*64
        corrupt[0]["observation_sha256"]=seal({
            k:v for k,v in corrupt[0].items() if k!="observation_sha256"})
        with self.assertRaisesRegex(ValueError,"original sealed"):
            build(policy,future,macro,[doc],corrupt,at("2026-11-13T20:30:00"))

    def test_source_days_cannot_come_from_future_fx_history(self):
        policy,fx,quotes,macro=fixture()
        with self.assertRaisesRegex(ValueError,"future dated"):
            build(policy,fx,macro,[],[],at("2026-11-05T18:00:00"))


if __name__=="__main__":
    unittest.main()
