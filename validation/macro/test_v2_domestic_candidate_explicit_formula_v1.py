"""Adversarial offline economic formula test; no tradable Core mutation."""
import copy
import json
import math
import unittest
from pathlib import Path

from validation.macro.v2_g8_three_axis_economic_shadow_v1 import run as shadow_run
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    build,run,activity_class,indicative_regime,continuous_weight_interval,
    independent_axis_revision_envelope, REVISION_STRESS_EPSILONS_Z, G8,FORMULA
)


class CandidateFormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shadow=shadow_run(as_of="2026-10-27")
        cls.legacy=json.loads((Path(__file__).resolve().parents[2]/
                              "live_data/sections/D.json").read_text())

    def test_real_8_by_3_candidate_is_separately_versioned_not_live(self):
        result=build(self.shadow,self.legacy)
        self.assertEqual(result["formula_version"],FORMULA)
        self.assertEqual(set(result["countries"]),set(G8))
        self.assertEqual(result["summary"]["axes"],24)
        self.assertEqual(result["summary"]["D_json_rebuilt"],False)
        self.assertEqual(result["summary"]["FX_scores_produced"],0)
        self.assertEqual(result["summary"]["28_pair_theses_recomputed"],0)
        self.assertFalse(result["safe_to_publish_D"])
        self.assertFalse(result["safe_to_update_pair_theses"])
        self.assertFalse(result["safe_to_use_for_beta"])
        self.assertFalse(result["safe_to_use_for_forward"])
        self.assertFalse(result["writes_live_data"])
        self.assertFalse(result["canonical_core_score_formula_recovered"])
        self.assertTrue(result["out_of_sample_falsification_not_completed"])
        for x in result["countries"].values():
            self.assertAlmostEqual(x["domestic_activity_candidate_z"],
                                   .5*x["growth_within_history_z"]+
                                   .5*x["unemployment_tightness_within_history_z"],
                                   places=10)
            self.assertEqual(x["growth_weight_sensitivity_z"]["50"],
                             x["domestic_activity_candidate_z"])
            self.assertIsNone(x["FX_strength_candidate"])
            self.assertTrue(x["legacy_D_numbers_are_NOT_in_new_candidate_units"])

    def test_US_estimation_and_EUR_CHF_definition_caveats_not_hidden(self):
        r=build(self.shadow,self.legacy)["countries"]
        self.assertTrue(r["USD"]["source_quality_details"]["labour"]["is_estimate"])
        self.assertTrue(r["USD"]["source_quality_details"]["inflation"]["is_estimate"])
        self.assertTrue(r["EUR"]["source_quality_flags"])
        self.assertTrue(r["CHF"]["source_quality_flags"])
        self.assertFalse(r["CAD"]["source_quality_flags"])

    def test_continuous_weight_range_is_not_cherry_picked(self):
        r=build(self.shadow,self.legacy)
        for ccy,row in r["countries"].items():
            z=row["continuous_weight_sensitivity_RESEARCH_ONLY"]
            g=row["growth_within_history_z"]
            l=row["unemployment_tightness_within_history_z"]
            left=0.25*g+0.75*l
            right=0.75*g+0.25*l
            self.assertEqual(z["growth_weight_interval_inclusive"],[0.25,0.75])
            self.assertAlmostEqual(z["domestic_activity_z_min"],min(left,right),places=10)
            self.assertAlmostEqual(z["domestic_activity_z_max"],max(left,right),places=10)
            self.assertEqual(z["continuous_weight_math_is_NOT_PIT_or_FX_validation"],True)
            stable=(activity_class(left)==activity_class(.5*g+.5*l)==activity_class(right))
            self.assertEqual(z["classification_unchanged_at_every_weight_in_interval"],stable,ccy)
            self.assertEqual(z["weight_invariant_domestic_class_RESEARCH_ONLY"],
                activity_class(.5*g+.5*l) if stable else None,ccy)
            self.assertEqual(stable,row["activity_class_stable_across_25_50_75pct_growth"])
            self.assertIsNone(row["FX_strength_candidate"])
        self.assertEqual(
            r["summary"]["countries_weight_ambiguous_no_robust_class"],
            r["summary"]["countries_unstable_to_weights"])
        self.assertEqual(
            r["summary"]["countries_robust_for_ALL_continuous_weights_25_75pct"]+
            r["summary"]["countries_weight_ambiguous_no_robust_class"],8)
        # Synthetic economic inputs exercise threshold equality and a range
        # crossing both +0.5 and -0.5. Never select the 'best' outcome post hoc.
        case=continuous_weight_interval(1,-1)
        self.assertEqual(case["domestic_activity_z_min"],-0.5)
        self.assertEqual(case["domestic_activity_z_max"],0.5)
        self.assertIsNone(case["weight_invariant_domestic_class_RESEARCH_ONLY"])
        self.assertTrue(case["class_changes_with_admissible_weights"])
        for growth,labour,expected in [
                (1,1,"FIRM_RELATIVE_TO_OWN_HISTORY"),
                (-1,-1,"SOFT_RELATIVE_TO_OWN_HISTORY"),
                (0.1,0.2,"MIXED_RELATIVE_TO_OWN_HISTORY"),
                (0.5,0.5,"FIRM_RELATIVE_TO_OWN_HISTORY")]:
            z=continuous_weight_interval(growth,labour)
            self.assertTrue(z["classification_unchanged_at_every_weight_in_interval"])
            self.assertEqual(z["weight_invariant_domestic_class_RESEARCH_ONLY"],expected)
        for invalid in (float("nan"),float("inf"),3.1):
            with self.assertRaises(ValueError):
                continuous_weight_interval(invalid,0)

    def test_independent_revision_stress_is_mathematical_not_empirical(self):
        self.assertEqual(REVISION_STRESS_EPSILONS_Z, (0.10, 0.25, 0.50))
        for g, l, eps, lower, upper in [
            (0.30, 0.30, 0.10, 0.20, 0.40),
            (0.30, 0.30, 0.25, 0.05, 0.55),
            (1.00, 1.00, 0.50, 0.50, 1.50),
            (1.00, -1.00, 0.25, -0.75, 0.75),
        ]:
            with self.subTest(g=g, l=l, eps=eps):
                x=independent_axis_revision_envelope(g,l,eps)
                self.assertAlmostEqual(x["stressed_activity_z_min"],lower)
                self.assertAlmostEqual(x["stressed_activity_z_max"],upper)
                self.assertTrue(x["this_is_not_an_empirical_revision_error_estimate"])
                self.assertTrue(x["not_a_PIT_or_FX_forecast_test"])
        self.assertTrue(independent_axis_revision_envelope(
            0.30,0.30,0.10)["class_invariant_to_all_weights_and_independent_axis_shifts"])
        self.assertFalse(independent_axis_revision_envelope(
            0.30,0.30,0.25)["class_invariant_to_all_weights_and_independent_axis_shifts"])
        self.assertEqual(independent_axis_revision_envelope(
            1,1,0.50)["robust_domestic_class_RESEARCH_ONLY"],
            "FIRM_RELATIVE_TO_OWN_HISTORY")
        for eps in [-1, 0.51, float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                independent_axis_revision_envelope(0.2,0.3,eps)

    def test_g8_stress_nested_without_promoting_FX(self):
        out=build(self.shadow,self.legacy)
        self.assertTrue(out["revision_stress_is_hypothetical_not_data_calibrated"])
        counts=[]
        for key in ("10","25","50"):
            valid=0
            for ccy,row in out["countries"].items():
                diag=row["hypothetical_axis_revision_stress_RESEARCH_ONLY"][key]
                self.assertTrue(diag["this_is_not_an_empirical_revision_error_estimate"])
                self.assertTrue(diag["not_a_PIT_or_FX_forecast_test"])
                self.assertIsNone(row["FX_strength_candidate"])
                robust=diag["class_invariant_to_all_weights_and_independent_axis_shifts"]
                if robust:
                    self.assertTrue(row["activity_class_stable_across_25_50_75pct_growth"])
                    self.assertEqual(diag["robust_domestic_class_RESEARCH_ONLY"],
                                     row["domestic_activity_class"])
                else:
                    self.assertIsNone(diag["robust_domestic_class_RESEARCH_ONLY"])
                valid+=robust
            counts.append(valid)
        self.assertGreaterEqual(counts[0],counts[1])
        self.assertGreaterEqual(counts[1],counts[2])
        self.assertLessEqual(counts[0],4)
        self.assertEqual(counts[0],out["summary"][
            "countries_robust_hypothetical_axis_shift_0p10_z"])
        self.assertEqual(counts[1],out["summary"][
            "countries_robust_hypothetical_axis_shift_0p25_z"])
        self.assertEqual(counts[2],out["summary"][
            "countries_robust_hypothetical_axis_shift_0p50_z"])
        self.assertEqual(out["summary"]["FX_scores_produced"],0)
        self.assertFalse(out["safe_to_publish_D"])
        print("G8_HYPOTHETICAL_REVISION_STRESS_COUNTS_10_25_50",counts)

    def test_inflation_is_separate_no_false_growth_increase(self):
        a=build(self.shadow,self.legacy)["countries"]["CAD"]
        modified=copy.deepcopy(self.shadow)
        old=modified["countries"]["CAD"]["inflation_pressure_relative_to_own_history_z"]
        modified["countries"]["CAD"]["inflation_pressure_relative_to_own_history_z"]=(-3 if old>0 else 3)
        b=build(modified,self.legacy)["countries"]["CAD"]
        self.assertEqual(a["domestic_activity_candidate_z"],b["domestic_activity_candidate_z"])
        self.assertNotEqual(a["inflation_pressure_within_history_z"],b["inflation_pressure_within_history_z"])

    def test_source_score_and_future_age_cannot_be_forged(self):
        for bad_path,value in [
            (("safe_to_publish_new_D",),True),
            (("countries","GBP","approved_for_live_core_D"),True),
            (("countries","JPY","fx_directional_bias"),"LONG"),
            (("countries","EUR","growth_relative_to_own_history_z"),float("nan")),
            (("scope","activity_weights"),{"growth":1,"labour_tightness":0,"inflation_in_activity":0}),
        ]:
            with self.subTest(path=bad_path):
                wrong=copy.deepcopy(self.shadow)
                node=wrong
                for k in bad_path[:-1]:node=node[k]
                node[bad_path[-1]]=value
                with self.assertRaises(ValueError):
                    build(wrong,self.legacy)
        wrong=copy.deepcopy(self.legacy)
        wrong["asOf"]="2027-01-01"
        with self.assertRaises(ValueError): build(self.shadow,wrong)

    def test_sensitivity_class_and_neutral_regime_not_forced(self):
        self.assertEqual(activity_class(0.1),"MIXED_RELATIVE_TO_OWN_HISTORY")
        self.assertEqual(indicative_regime(0.1,2),
                         "MIXED_OR_TURNING_DOMESTIC_CYCLE")
        self.assertEqual(indicative_regime(.75,-.9),
                         "FIRM_GROWTH_WITH_SUBDUED_PRICE_PRESSURE")
        self.assertEqual(indicative_regime(-.75,.9),
                         "SOFT_GROWTH_WITH_ELEVATED_PRICE_PRESSURE")
        self.assertEqual(indicative_regime(-.75,-.9),
                         "SOFT_GROWTH_WITH_SUBDUED_PRICE_PRESSURE")

    def test_repository_inputs_not_mutated(self):
        root=Path(__file__).resolve().parents[2]
        paths=[root/"live_data/sections/D.json",
               root/"live_data/sections/MACRO_SERIES.json",
               root/"live_data/sections/MACRO_THERMOMETER_DATA.json"]
        before={str(x):x.read_bytes() for x in paths}
        out=run(as_of="2026-10-27")
        self.assertEqual(out["economic_as_of"],"2026-10-27")
        self.assertEqual({str(x):x.read_bytes() for x in paths},before)


if __name__=="__main__": unittest.main()
