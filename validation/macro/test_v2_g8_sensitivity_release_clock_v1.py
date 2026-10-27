"""Adversarial regressions for GDP cutoff clocks + economic weight sensitivity."""
from __future__ import annotations

import copy
import math
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_sensitivity_release_clock_v1 import (
    FX, REPLAY_QUARTERS, SCHEMA, STRESS_Z, WEIGHT_GROWTH, activity,
    audit, gdp_publication_clock_replay, sensitivity
)
from validation.macro.v2_g8_gdp_unified_web_research_v1 import unified_research_rows
from validation.macro.v2_g8_three_axis_economic_shadow_v1 import run as run_three_axis
from validation.macro.v2_g8_observed_feature_bridge_v1 import ROOT


class EconomicSensitivityAndGdpClocks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        cls.three = run_three_axis(as_of=cls.today)
        cls.rows = unified_research_rows()

    def test_exactly_64_historical_GDP_release_date_cutoffs(self):
        r = gdp_publication_clock_replay(self.rows)
        self.assertEqual(r["summary"]["g8_currencies"], 8)
        self.assertEqual(r["summary"]["first_web_currency_quarter_cases"], 64)
        self.assertEqual(len(REPLAY_QUARTERS), 8)
        for c in FX:
            records = r["countries"][c]["quarterly_first_web_research_replays"]
            self.assertEqual([x["reference_quarter"] for x in records],
                             list(REPLAY_QUARTERS))
            self.assertTrue(all(x["first_web_release_clock_cutoff_obeyed"]
                                for x in records))
            self.assertTrue(all(x["first_web_training_excludes_same_quarter"]
                                for x in records))
            self.assertFalse(r["countries"][c]["valid_joint_macro_asof_replay"])
            self.assertFalse(r["countries"][c]["valid_FX_backtest"])
            self.assertTrue(all(-3 <= x["first_web_descriptive_growth_z"] <= 3
                                for x in records))

    def test_current_sensitivity_3_weights_and_inputs_are_descriptive_only(self):
        r = sensitivity(self.three)
        self.assertEqual(r["summary"]["currencies"], 8)
        self.assertEqual(r["summary"]["within_country_weights_per_currency"], 3)
        self.assertEqual(tuple(r["weights_tested_growth"]), WEIGHT_GROWTH)
        self.assertEqual(r["shock_axis_change_z"], STRESS_Z)
        self.assertTrue(r["shock_size_is_scenario_not_estimated_measurement_error"])
        self.assertTrue(r["no_cross_currency_ranking_authorized"])
        for c in FX:
            x = r["countries"][c]
            self.assertEqual(len(x["alternative_weights_growth_25_50_75"]), 3)
            self.assertEqual(len(x["one_axis_plus_minus_0_25z_shocks"]), 4)
            self.assertIsNone(x["live_currency_score"])
            self.assertFalse(x["pair_ranking_eligible"])
            self.assertFalse(x["estimated_uncertainty_interval"])
            self.assertTrue(x["one_country_only_not_cross_currency_comparable"])
        self.assertEqual(r["summary"]["FX_rankings_computed"], 0)

    def test_linear_growth_weight_stress_has_correct_math(self):
        r = sensitivity(self.three)
        for c in FX:
            row = self.three["countries"][c]
            g, l = (row["growth_relative_to_own_history_z"],
                    row["labour_tightness_relative_to_own_history_z"])
            alt = r["countries"][c]["alternative_weights_growth_25_50_75"]
            self.assertAlmostEqual(alt["growth_25pct"], .25*g+.75*l, places=10)
            self.assertAlmostEqual(alt["growth_50pct"], .5*g+.5*l, places=10)
            self.assertAlmostEqual(alt["growth_75pct"], .75*g+.25*l, places=10)
            self.assertAlmostEqual(alt["growth_75pct"]-alt["growth_25pct"],
                                   0.5*(g-l), places=10)

    def test_inflation_independent_of_activity_in_all_weight_variants(self):
        base = sensitivity(self.three)
        changed = copy.deepcopy(self.three)
        old = changed["countries"]["GBP"]["inflation_pressure_relative_to_own_history_z"]
        changed["countries"]["GBP"]["inflation_pressure_relative_to_own_history_z"] = (
            3.0 if old <= 0 else -3.0)
        r = sensitivity(changed)
        self.assertEqual(
            base["countries"]["GBP"]["alternative_weights_growth_25_50_75"],
            r["countries"]["GBP"]["alternative_weights_growth_25_50_75"])
        self.assertNotEqual(base["countries"]["GBP"]["inflation_pressure_z_stays_separate"],
                            r["countries"]["GBP"]["inflation_pressure_z_stays_separate"])

    def test_high_weights_must_not_become_fx_score_or_model_promotions(self):
        fake = copy.deepcopy(self.three)
        fake["countries"]["CAD"]["fx_currency_strength_score"] = 0.8
        with self.assertRaisesRegex(ValueError, "unknown or promoted"):
            sensitivity(fake)
        fake = copy.deepcopy(self.three)
        fake["scope"]["activity_weights"]["inflation_in_activity"] = .2
        with self.assertRaisesRegex(ValueError, "baseline weights"):
            sensitivity(fake)
        fake = copy.deepcopy(self.three)
        fake["summary"]["FX_scores_approved"] = 8
        with self.assertRaisesRegex(ValueError, "remain research-only"):
            sensitivity(fake)

    def test_nonfinite_and_spoofed_currency_inputs_fail_closed(self):
        fake = copy.deepcopy(self.three)
        fake["countries"]["JPY"]["growth_relative_to_own_history_z"] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite economic"):
            sensitivity(fake)
        fake = copy.deepcopy(self.three)
        fake["countries"]["NZD"]["currency"] = "CAD"
        with self.assertRaisesRegex(ValueError, "unknown or promoted"):
            sensitivity(fake)
        fake = copy.deepcopy(self.three)
        fake["countries"]["CHF"]["illustrative_activity_labour_balance_z"] = 888
        with self.assertRaisesRegex(ValueError, "disagrees"):
            sensitivity(fake)

    def test_missing_one_first_web_GDP_quarter_blocks_historical_replay(self):
        bad = [x for x in self.rows if not
               (x["currency"] == "AUD" and x["reference_quarter"] == "2025Q3"
                and x["stage_order"] == 0)]
        with self.assertRaisesRegex(ValueError, "complete eight-country"):
            gdp_publication_clock_replay(bad)

    def test_revision_does_not_change_original_first_web_research(self):
        original = gdp_publication_clock_replay(self.rows)
        altered = copy.deepcopy(self.rows)
        row = next(x for x in altered if
                   x["currency"] == "USD" and x["reference_quarter"] == "2026Q2"
                   and x["stage_order"] == 2)
        row["reported_value"] = 2.9   # hypothetical changed followup statement
        changed = gdp_publication_clock_replay(altered)
        self.assertEqual(
            original["countries"]["USD"]["quarterly_first_web_research_replays"],
            changed["countries"]["USD"]["quarterly_first_web_research_replays"])

    def test_original_web_source_url_issuer_mismatch_rejected(self):
        altered = copy.deepcopy(self.rows)
        row = next(x for x in altered if x["currency"] == "NZD" and
                   x["reference_quarter"] == "2026Q2" and x["stage_order"] == 0)
        row["source_url"] = "https://untrusted.example/not-an-official-release"
        with self.assertRaisesRegex(ValueError, "publisher host"):
            gdp_publication_clock_replay(altered)

    def test_full_pipeline_artifact_and_no_D_or_pair_changes(self):
        protected = ROOT / "live_data/sections"
        before = {name: (protected / name).read_bytes() for name in (
            "D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")}
        r = audit(as_of=self.today, gdp_rows=self.rows, three_axis=self.three)
        after = {name: (protected / name).read_bytes() for name in before}
        self.assertEqual(before, after)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["summary"]["GDP_release_clock_cases"], 64)
        self.assertEqual(r["summary"]["FX_out_of_sample_trials"], 0)
        self.assertEqual(r["summary"]["certified_macro_scores"], 0)
        self.assertTrue(r["macro_labour_inflation_historic_pit_replay_still_missing"])
        self.assertTrue(r["no_trading_edge_or_predictive_performance_demonstrated"])
        self.assertFalse(r["safe_to_publish_new_D"])
        self.assertFalse(r["safe_to_update_pair_theses"])
        self.assertFalse(r["safe_to_use_for_beta"])
        self.assertFalse(r["safe_to_use_for_forward"])
        self.assertFalse(r["writes_live_data"])


if __name__ == "__main__":
    unittest.main()
