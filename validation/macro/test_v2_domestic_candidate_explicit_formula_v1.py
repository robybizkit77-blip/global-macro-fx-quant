"""Adversarial offline economic formula test; no tradable Core mutation."""
import copy
import json
import math
import unittest
from pathlib import Path

from validation.macro.v2_g8_three_axis_economic_shadow_v1 import run as shadow_run
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    build,run,activity_class,indicative_regime,G8,FORMULA
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
