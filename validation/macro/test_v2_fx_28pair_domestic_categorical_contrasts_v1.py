"""Tests of scenario robustness: domestic class contrasts never equal FX signals."""
from __future__ import annotations
import copy
import json
import unittest
from collections import Counter

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import run as domestic_run
from validation.macro.v2_fx_28pair_synchronized_evidence_gate_v1 import run as source_run
from validation.macro.v2_fx_28pair_domestic_categorical_contrasts_v1 import (
    FIRM, SOFT, MIXED, NO_CONTRAST, ROOT, compute, contrast_values,
    contrast_classes, run
)

class DomesticContrastScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate=domestic_run(as_of="2026-10-27")
        cls.source=source_run(as_of="2026-10-28")
        cls.r=compute(candidate=cls.candidate,source=cls.source)

    def bad(self,which,change):
        d=copy.deepcopy(getattr(self,which))
        change(d)
        args={"candidate":self.candidate,"source":self.source}
        args[which]=d
        with self.assertRaises(ValueError):compute(**args)

    def test_descriptive_28_pair_scenario_partition_no_price_ranking(self):
        r=self.r
        s=r["summary"]
        self.assertEqual(s["countries"],8)
        self.assertEqual(s["pairs"],28)
        self.assertEqual(s["scenarios_per_pair"],3)
        self.assertEqual(s["country_weight_unstable_count"],4)
        self.assertEqual(s["country_weight_unstable"],["AUD","CHF","NZD","USD"])
        self.assertEqual(
            s["pairs_persistent_opposed_categories"]+
            s["pairs_weight_sensitive_opposed_categories"]+
            s["pairs_no_opposed_categories"],28)
        self.assertEqual(s["pairs_all_2Y_6m_OIS_exact_same_day"],0)
        self.assertEqual(s["FX_directional_signals"],0)
        self.assertEqual(s["relative_strength_rankings"],0)
        self.assertEqual(s["out_of_sample_predictions_evaluated"],0)
        self.assertTrue(r["country_specific_history_z_magnitudes_not_subtracted"])
        self.assertTrue(r["no_tuning_to_future_FX_returns"])
        for pair,rec in r["scenario_pair_rows"].items():
            self.assertEqual(pair,rec["pair"])
            self.assertIsNone(rec["macro_relative_FX_score"])
            self.assertIsNone(rec["macro_relative_FX_rank"])
            self.assertIsNone(rec["official_OIS_6m_weekly_relative_repricing_FX"])
            self.assertFalse(rec["can_emit_bias_or_trade"])
            self.assertFalse(rec["eligible_for_forward_or_beta"])
            self.assertFalse(rec["eligible_for_historical_PIT_backtest"])
            self.assertEqual(list(rec["scenario_outcomes"]),["25","50","75"])
            for x in rec["scenario_outcomes"].values():
                self.assertIn(x["categorical_economic_contrast_ONLY"],
                    ("BASE_FIRM_QUOTE_SOFT","BASE_SOFT_QUOTE_FIRM",NO_CONTRAST))

    def test_firm_soft_only_and_pair_orientation_symmetry(self):
        self.assertEqual(contrast_classes(FIRM,SOFT),"BASE_FIRM_QUOTE_SOFT")
        self.assertEqual(contrast_classes(SOFT,FIRM),"BASE_SOFT_QUOTE_FIRM")
        self.assertEqual(contrast_classes(FIRM,MIXED),NO_CONTRAST)
        self.assertEqual(contrast_classes(FIRM,FIRM),NO_CONTRAST)
        self.assertEqual(contrast_classes(MIXED,SOFT),NO_CONTRAST)
        self.assertEqual(contrast_classes(MIXED,MIXED),NO_CONTRAST)
        self.assertEqual(contrast_values(.51,-.51),"BASE_FIRM_QUOTE_SOFT")
        self.assertEqual(contrast_values(-.51,.51),"BASE_SOFT_QUOTE_FIRM")
        self.assertEqual(contrast_values(.49,-.51),NO_CONTRAST)
        self.assertEqual(contrast_values(.51,-.49),NO_CONTRAST)
        self.assertEqual(contrast_values(1.5,.49),NO_CONTRAST)
        with self.assertRaises(ValueError):contrast_values(float("nan"),1.0)
        with self.assertRaises(ValueError):contrast_values(float("inf"),1.0)

    def test_all_three_scenarios_stability_recomputed(self):
        for pair,r in self.r["scenario_pair_rows"].items():
            a,b=pair.split("/")
            A,B=self.candidate["countries"][a],self.candidate["countries"][b]
            outcomes=[]
            for w in ("25","50","75"):
                exp=contrast_values(A["growth_weight_sensitivity_z"][w],
                                    B["growth_weight_sensitivity_z"][w])
                self.assertEqual(
                    r["scenario_outcomes"][w]["categorical_economic_contrast_ONLY"],exp)
                outcomes.append(exp)
            persistent=len(set(outcomes))==1 and NO_CONTRAST not in outcomes
            self.assertEqual(r["persistent_opposed_category_all_weights"],persistent)
            self.assertEqual(r["some_opposite_category_but_not_all_scenarios"],
                             not persistent and any(x!=NO_CONTRAST for x in outcomes))

    def test_estimates_retained_and_no_fabricated_ois_or_want_can(self):
        d=self.r["scenario_pair_rows"]
        self.assertTrue(d["EUR/USD"]["has_any_estimate_or_definition_caveat"])
        self.assertTrue(d["EUR/CHF"]["has_any_estimate_or_definition_caveat"])
        self.assertFalse(d["CAD/JPY"]["has_any_estimate_or_definition_caveat"])
        self.assertFalse(d["EUR/USD"]["official_6m_both_same_date"])
        self.assertFalse(d["GBP/JPY"]["official_6m_both_same_date"])
        self.assertTrue(d["AUD/JPY"]["official_6m_both_same_date"])
        self.bad("source",lambda x:x.update(safe_to_recalculate_28_pairs=True))
        self.bad("source",lambda x:x["pair_evidence"]["EUR/USD"].update(
            macro_strength_diff_z=0.4))
        self.bad("source",lambda x:x["pair_evidence"]["EUR/USD"].update(
            CB_Want_Can_pair_comparison_validated=True))
        self.bad("candidate",lambda x:x["countries"]["JPY"].update(
            FX_strength_candidate=0.5))
        self.bad("candidate",lambda x:x["countries"]["JPY"].update(
            growth_weight_sensitivity_z={"25":-2.0,"50":-1.0,"75":1.0}))
        self.bad("candidate",lambda x:x["countries"]["CHF"].update(
            inflation_pressure_within_history_z=float("nan")))
        self.bad("candidate",lambda x:x.update(out_of_sample_falsification_not_completed=False))

    def test_deterministic_and_no_live_or_forward_mutation(self):
        paths=[
            ROOT/"live_data/sections/D.json",
            ROOT/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
            ROOT/"live_data/sections/OIS_OPERATIONAL_VIEW.json",
            ROOT/"validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl",
        ]
        before={str(x):x.read_bytes() for x in paths}
        again=run()
        self.assertEqual(self.r["receipt_sha256"],again["receipt_sha256"])
        self.assertEqual(before,{str(x):x.read_bytes() for x in paths})
        for k in ("safe_to_publish_new_D","safe_to_change_28_pair_states",
                  "safe_to_use_for_beta","safe_to_use_for_forward","writes_live_data"):
            self.assertFalse(again[k])
        with self.assertRaises(ValueError):run("2026-10-29")

if __name__=="__main__":unittest.main()
