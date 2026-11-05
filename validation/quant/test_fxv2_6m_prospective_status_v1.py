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

    def test_missing_ecb_fixing_after_evening_does_not_remain_awaiting(self):
        policy,fx,quotes,macro=fixture()
        fx["rows"].pop()
        fx["last_as_of"]="2026-11-05"
        fx["row_count"]=len(fx["rows"])
        before=build(policy,fx,macro,[],[],
                     at("2026-11-06T20:44:00"),quotes)
        self.assertEqual(before["report_status"],
                         "AWAITING_FIRST_ACTUAL_EVENING_SNAPSHOT")
        self.assertFalse(before["input_readiness"]["capture_due_but_missing"])
        after=build(policy,fx,macro,[],[],
                    at("2026-11-06T20:46:00"),quotes)
        self.assertEqual(after["report_status"],
                         "CAPTURE_BLOCKED_MISSING_SAME_DAY_ECB_FIXING_ATTENTION")
        self.assertTrue(after["input_readiness"]["capture_due_but_missing"])
        self.assertFalse(after["input_readiness"]["official_ecb_t0_available_for_rome_day"])
        self.assertEqual(after["summary"]["actual_prospective_capture_days"],0)
        self.assertFalse(after["eligible_for_predictive_claim"])

    def test_ecb_available_without_actual_freeze_is_missed_capture(self):
        policy,fx,quotes,macro=fixture()
        report=build(policy,fx,macro,[],[],
                     at("2026-11-06T20:46:00"),quotes)
        self.assertEqual(report["report_status"],
                         "CAPTURE_MISSED_WITH_SAME_DAY_ECB_AVAILABLE_ATTENTION")
        self.assertTrue(report["input_readiness"]["capture_due_but_missing"])
        self.assertTrue(report["input_readiness"]["official_ecb_t0_available_for_rome_day"])
        doc,_=freeze(at("2026-11-06T20:49:00"),policy,fx,quotes,macro,[])
        recovered=build(policy,fx,macro,[doc],[],
                        at("2026-11-06T20:50:00"),quotes)
        self.assertFalse(recovered["input_readiness"]["capture_due_but_missing"])
        self.assertTrue(recovered["input_readiness"]["prospective_capture_already_frozen_for_rome_day"])
        self.assertEqual(recovered["report_status"],
                         "PROSPECTIVE_COLLECTION_IN_PROGRESS_NOT_VALIDATED")

    def test_quote_inspection_never_uses_future_first_seen_and_never_predicts(self):
        policy,fx,quotes,macro=fixture()
        moment=at("2026-11-06T20:50:00")
        valid=build(policy,fx,macro,[],[],moment,quotes)
        inventory=valid["input_readiness"]["last_valid_6m_source_audit"]
        self.assertTrue(inventory["available"])
        self.assertTrue(inventory["no_forecast_generated"])
        self.assertEqual(set(inventory["pair_recent_same_contract_source"]),
                         {"EUR/USD","EUR/CHF","USD/CHF"})
        self.assertEqual(inventory["source_as_of_last_available_ecb_fixing"],
                         "2026-11-06")
        self.assertTrue(inventory["pair_recent_same_contract_source"]["USD/CHF"][
                         "has_recent_matched_same_contract_6m_quote_change"])
        late=copy.deepcopy(quotes)
        for row in late:
            if row["currency"]=="CHF" and row["observed_under_horizon"]=="6m" and row["observation_date"]=="2026-11-04":
                row["first_seen_at_utc"]="2026-11-06T23:30:00Z"
        future=build(policy,fx,macro,[],[],moment,late)
        self.assertFalse(future["input_readiness"]["last_valid_6m_source_audit"][
                         "pair_recent_same_contract_source"]["USD/CHF"][
                         "has_recent_matched_same_contract_6m_quote_change"])
        self.assertEqual(future["summary"]["experimental_direction_observations"],0)
        self.assertFalse(future["predictive_skill_validated"])

    def test_source_days_cannot_come_from_future_fx_history(self):
        policy,fx,quotes,macro=fixture()
        with self.assertRaisesRegex(ValueError,"future dated"):
            build(policy,fx,macro,[],[],at("2026-11-05T18:00:00"))


if __name__=="__main__":
    unittest.main()
