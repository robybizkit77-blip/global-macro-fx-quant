"""Adversarial USD/CHF research-only joint source-quality stress tests."""
from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from validation.macro.v2_us_chf_source_quality_propagation_v1 import (
    evaluate, run, CANDIDATE_DATE,
)
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    activity_class, run as candidate_run,
)
from validation.macro.v2_us_cpi_prior24_issuer_revised_sensitivity_v1 import (
    audit as us_audit,
)
from validation.macro.v2_chf_seco_first_month_rounded_alternative_v1 import (
    audit as chf_audit,
)

ROOT = Path(__file__).resolve().parents[2]


class TwoSourceResearchQualityPropagation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = candidate_run(as_of=CANDIDATE_DATE)
        cls.us = us_audit()
        cls.chf = chf_audit()
        cls.result = evaluate(cls.candidate, cls.us, cls.chf)

    def test_us_24_in_25_issuer_revised_not_pit_but_class_testable(self):
        us = self.result["USD_inflation"]
        self.assertEqual(us["training_observations"], 24)
        self.assertEqual(us["training_calendar_months"], 25)
        self.assertEqual(us["unpublished_period"], "2025-10")
        self.assertAlmostEqual(us["issuer_minus_revised_z"],
                               self.us["summary"]["robust_z_candidate_minus_revised"], places=9)
        self.assertTrue(us["same_descriptive_inflation_class_for_two_non_PIT_sources"])
        self.assertFalse(us["first_release_day_original_binary_certified"])
        self.assertFalse(us["strict_consecutive_PIT_training_eligible"])
        self.assertFalse(us["can_replace_candidate_inflation_z"])
        self.assertTrue(us["inflation_is_separate_from_domestic_activity"])

    def test_chf_rounded_first_source_interval_propagates_without_snb_alias(self):
        ch = self.result["CHF_labour"]
        r = self.chf["statistical_research"]["hypothetical_unrounded_SECO_precision_envelope"]
        g = self.candidate["countries"]["CHF"]["growth_within_history_z"]
        lo, hi = r["descriptive_robust_z_clipped_conservative_interval"]
        self.assertEqual(ch["hypothetical_precise_seco_unemployment_z_bounds"], [lo, hi])
        self.assertEqual(ch["hypothetical_fixed_50_50_activity_interval"],
                         [.5*g-.5*hi, .5*g-.5*lo])
        corners = [w*g-(1-w)*z for w in (.25, .75) for z in (lo, hi)]
        self.assertEqual(ch["hypothetical_25_to_75_growth_weight_activity_interval"],
                         [min(corners),max(corners)])
        self.assertEqual(ch["fixed_weight_class_not_guaranteed_by_print_precision"],
                         activity_class(.5*g-.5*hi) != activity_class(.5*g-.5*lo))
        self.assertEqual(ch["joint_weight_and_print_precision_class_not_guaranteed"],
                         activity_class(min(corners)) != activity_class(max(corners)))
        self.assertFalse(ch["source_can_be_equated_to_original_SNB_precise_series"])
        self.assertFalse(ch["safe_to_replace_candidate_labour_axis"])
        self.assertEqual(ch["exact_historical_snb_source_day_vintages"], 0)
        self.assertEqual((ch["seco_original_first_report_pdf_bytes_downloaded_now"],
                          ch["seco_2024_report_text_index_only"]), (21, 4))

    def test_incomplete_source_policy_does_not_invent_macro_fx_signals(self):
        r = self.result
        self.assertEqual(r["summary"]["residual_source_quality_cases"], 2)
        self.assertEqual(r["summary"]["source_day_training_vintage_series_certified"], 0)
        self.assertEqual(r["summary"]["candidate_macro_scores_authorized"], 0)
        self.assertEqual(r["summary"]["pair_rankings_recomputed"], 0)
        for k in ("safe_to_publish_new_D","safe_to_recalculate_28_pairs",
                  "safe_for_beta","safe_for_forward","writes_live_data"):
            self.assertIs(r[k],False)

    def test_not_promotable_even_with_one_stable_us_price_class(self):
        bad = copy.deepcopy(self.us)
        bad["24_prior_observed_not_24_consecutive"] = False
        with self.assertRaises(ValueError):
            evaluate(self.candidate,bad,self.chf)
        bad = copy.deepcopy(self.us)
        bad["summary"]["issuer_original_day_binary_certifications"] = 24
        with self.assertRaises(ValueError):
            evaluate(self.candidate,bad,self.chf)
        bad = copy.deepcopy(self.chf)
        bad["summary"]["original_PDF_bytes_still_missing_despite_indexed_text"] = 0
        with self.assertRaises(ValueError):
            evaluate(self.candidate,self.us,bad)
        bad = copy.deepcopy(self.chf)
        bad["statistical_research"]["hypothetical_unrounded_SECO_precision_envelope"][
            "exact_SNB_amarbma_vintages_reconstructed"] = True
        with self.assertRaises(ValueError):
            evaluate(self.candidate,self.us,bad)
        bad = copy.deepcopy(self.candidate)
        bad["countries"]["CHF"]["FX_strength_candidate"] = 1.7
        with self.assertRaises(ValueError):
            evaluate(bad,self.us,self.chf)

    def test_output_reproducible_read_only_no_live_or_forward_files_changed(self):
        names = (
            "live_data/sections/D.json",
            "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
            "live_data/sections/MACRO_SERIES.json",
            "validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl",
        )
        before = {p: (ROOT/p).read_bytes() for p in names}
        x = run()
        y = run()
        self.assertEqual(x, y)
        self.assertEqual(x["status"],
                         "TWO_MISSING_CORE_SOURCE_QUALITY_STRESSED_NO_PIT_FX_PROMOTION")
        self.assertEqual(before, {p: (ROOT/p).read_bytes() for p in names})
        self.assertTrue(len(x["receipt_sha256"])==64)


if __name__ == "__main__":
    unittest.main()
