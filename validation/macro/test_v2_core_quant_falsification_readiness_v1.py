"""Adversarial quant readiness gate: math research != predictive PIT Beta/Forward."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import run as candidate_run
from validation.macro.v2_core_quant_falsification_readiness_v1 import (
    BETA, CORE, DECISIONS, FORWARD_SCHEMA, OUTCOMES, PAIR, RECEIPTS,
    ROOT, WALKFORWARD, _read_lines, evaluate, forward_inspect, run,
    receipt_reconciliation
)

class QuantFalsificationReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core=json.loads(CORE.read_text())
        cls.setup=json.loads(PAIR.read_text())
        cls.candidate=candidate_run(as_of="2026-10-27")
        cls.history=json.loads(WALKFORWARD.read_text())
        cls.decisions=_read_lines(DECISIONS)
        cls.forward=forward_inspect(json.loads(BETA.read_text()),
                                    json.loads(FORWARD_SCHEMA.read_text()),
                                    cls.decisions,_read_lines(OUTCOMES))
        cls.receipts=[json.loads(p.read_text()) for p in sorted(RECEIPTS.glob("*__*__V1.json"))]
        cls.result=cls.inspect()

    @classmethod
    def inspect(cls,**overrides):
        arguments={
            "candidate":cls.candidate,
            "forward":cls.forward,
            "history":cls.history,
            "core":cls.core,
            "setup":cls.setup,
            "receipts":cls.receipts,
            "decisions":cls.decisions
        }
        arguments.update(overrides)
        return evaluate(**arguments)

    def reject(self,field,change):
        obj=copy.deepcopy(getattr(self,field))
        change(obj)
        with self.assertRaises(ValueError):
            self.inspect(**{field:obj})

    def test_mathematical_formula_not_confused_with_FX_quant_backtest(self):
        r=self.result
        self.assertEqual(r["status"],
            "RESEARCH_QUANT_MATH_CHECKED__PIT_OOS_AND_OPERATIONAL_PROMOTION_BLOCKED")
        self.assertEqual(r["universe"]["currencies"],8)
        self.assertEqual(r["universe"]["canonical_unique_unordered_pairs"],28)
        self.assertEqual(r["formula_stress"]["economic_axes"],24)
        self.assertEqual(r["formula_stress"]["tested_growth_weights"],[0.25,0.5,0.75])
        self.assertEqual(r["summary"]["mathematical_research_gates_checked"],1)
        self.assertEqual(r["summary"]["unmet_or_blocked_launch_quant_gates"],6)
        self.assertEqual(r["summary"]["forward_observational_capture_gate_checked"],1)
        self.assertEqual(r["summary"]["new_core_scores_published"],0)
        self.assertEqual(r["summary"]["FX_pair_rankings_recomputed"],0)
        self.assertTrue(r["research_math_not_predictive_validation"])
        for flag in ("safe_to_publish_new_D","safe_to_recalculate_28_pairs",
                     "safe_to_claim_quantitative_predictive_validation",
                     "safe_to_claim_Beta_forward_OOS_success","writes_live_data"):
            self.assertFalse(r[flag])

    def test_receipts_not_equal_actual_persisted_forward_decisions(self):
        f=self.result["forward_truth"]
        self.assertGreaterEqual(len(f["receipt_records"]),3)
        self.assertEqual(f["realized_outcome_rows"],0)
        self.assertGreaterEqual(f["journal_unique_cutoffs"],3)
        self.assertEqual(f["journal_unique_cutoffs"],len({r["decision_cutoff"] for r in self.decisions}))
        self.assertGreaterEqual(f["journal_distinct_runs"],3)
        self.assertEqual(f["journal_distinct_runs"],len({r["run_id"] for r in self.decisions}))
        self.assertGreaterEqual(f["decision_rows_in_actual_journal"],84)
        self.assertEqual(f["decision_rows_in_actual_journal"],len(self.decisions))
        self.assertEqual(f["receipt_batches_claiming_written_rows_absent_from_journal"],0)
        self.assertFalse(f["some_receipts_do_not_establish_archived_decisions"])
        self.assertTrue(f["three_date_archived_forward_observations_reconciled"])
        unpaired=[x for x in f["receipt_records"] if x["unreconciled_claimed_writes"]>0]
        self.assertEqual(unpaired, [])
        self.assertEqual({x["run_id"] for x in f["receipt_records"]},
                         {r["run_id"] for r in self.receipts})
        self.assertTrue({"real-main-smoke-20261014", "frozen-core-20261026",
                         "frozen-core-20261027"}.issubset(
                         {x["run_id"] for x in f["receipt_records"]}))
        self.assertTrue(all(x["status"]=="MATCHED_JOURNAL_OR_ZERO_WRITES_NOT_PERFORMANCE"
                            and x["can_count_as_prospective_OOS_sample"] is False
                            for x in f["receipt_records"]))
        self.assertTrue(f["snapshots_not_equivalent_to_trading_evidence"])

    def test_legacy_revised_pseudo_OOS_cannot_be_new_formula_validation(self):
        h=self.result["historical_legacy_pseudo_OOS"]
        self.assertEqual(h["study_status"],"NO_RULE_CHANGE__PSEUDO_OOS_ONLY")
        self.assertTrue(h["cannot_reuse_as_new_domestic_formula_OOS"])
        self.assertFalse(h["proven_new_model_out_of_sample_performance"])
        self.assertFalse(self.result["beta_truth"]["strategy_beta_validated"])
        self.assertFalse(self.result["beta_truth"]["strict_OOS_variance_reduction_certified"])
        self.reject("history",lambda d:d.update(status="HISTORIC_PIT_CERTIFIED"))

    def test_inflation_not_added_to_domestic_activity_and_no_false_score(self):
        self.reject("candidate",lambda d:d["countries"]["USD"].update(
            domestic_activity_candidate_z=3))
        self.reject("candidate",lambda d:d["countries"]["USD"].update(
            FX_strength_candidate=2.6))
        self.reject("candidate",lambda d:d["countries"]["EUR"].update(
            eligible_to_recalculate_28_pairs=True))
        self.reject("candidate",lambda d:d["countries"]["CAD"].update(
            growth_weight_sensitivity_z={"25":0,"50":0,"75":0}))
        self.reject("candidate",lambda d:d.update(safe_to_publish_D=True))
        self.reject("candidate",lambda d:d.update(
            out_of_sample_falsification_not_completed=False))
        self.reject("candidate",lambda d:d.update(
            canonical_core_score_formula_recovered=True))

    def test_eight_currencies_28_pairs_and_stale_core_dated_safely(self):
        self.assertEqual(self.result["universe"]["macro_baseline_as_of"],"2026-09-25")
        self.assertEqual(self.result["universe"]["pair_price_as_of"],self.setup["price_asof"])
        self.assertFalse(self.result["universe"]["same_date_macro_and_fx_prices"])
        self.reject("core",lambda d:d.update(asOf="2026-10-27"))
        self.reject("setup",lambda d:d.update(pair_count=27))
        self.reject("setup",lambda d:d.update(
            macro_baseline_asof="2026-10-27"))
        self.reject("forward",lambda d:d.update(state="READY_FOR_LAUNCH"))
        self.reject("forward",lambda d:d["beta"].update(strategy_beta_validated=True))
        self.reject("forward",lambda d:d["forward"].update(decision_rows=len(self.decisions)+1))

    def test_archives_and_main_live_data_unchanged(self):
        paths=[
            CORE,
            PAIR,
            ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl",
            ROOT/"live_data/sections/MACRO_SERIES.json"
        ]
        before={str(p):p.read_bytes() for p in paths}
        again=run(as_of="2026-10-28")
        self.assertEqual(self.result["receipt_sha256"],again["receipt_sha256"])
        self.assertEqual(before,{str(p):p.read_bytes() for p in paths})
        with self.assertRaises(ValueError):
            run(as_of="2026-10-29")


if __name__=="__main__":
    unittest.main()
