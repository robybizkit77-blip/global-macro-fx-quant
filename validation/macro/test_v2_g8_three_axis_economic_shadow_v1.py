"""Pre-registration + adversarial regression for eight three-axis research cases."""
from __future__ import annotations

import copy
import math
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    FX, ROOT, run as observed_run
)
from validation.macro.v2_g8_three_axis_economic_shadow_v1 import (
    AXIS_THRESHOLD, VERSION, WEIGHTS, build, run
)


class ThreeAxisResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.as_of = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        cls.raw = observed_run(as_of=cls.as_of)

    def test_actual_eight_by_three_readonly_research_output(self):
        data = build(self.raw)
        self.assertEqual(set(data["countries"]), set(FX))
        self.assertEqual(data["summary"]["research_axes"], 24)
        self.assertEqual(data["summary"]["research_activity_balances_calculated"], 8)
        self.assertEqual(data["summary"]["macro_model_scores_approved"], 0)
        self.assertEqual(data["summary"]["FX_scores_approved"], 0)
        self.assertEqual(data["summary"]["pair_rankings_recalculated"], 0)
        self.assertEqual(data["version"], VERSION)
        self.assertEqual(data["scope"]["activity_weights"], WEIGHTS)
        self.assertEqual(AXIS_THRESHOLD, 0.5)
        self.assertFalse(data["safe_to_publish_new_D"])
        self.assertFalse(data["safe_to_update_pair_theses"])
        self.assertFalse(data["safe_for_beta"])
        self.assertFalse(data["safe_for_forward"])
        self.assertFalse(data["writes_live_data"])
        for c, row in data["countries"].items():
            self.assertEqual(set(row["dimensions"]), {"growth", "labour", "inflation"})
            for k in ("growth_relative_to_own_history_z",
                      "labour_tightness_relative_to_own_history_z",
                      "inflation_pressure_relative_to_own_history_z",
                      "illustrative_activity_labour_balance_z"):
                self.assertTrue(math.isfinite(row[k]), (c, k))
            self.assertAlmostEqual(
                row["illustrative_activity_labour_balance_z"],
                (row["growth_relative_to_own_history_z"] +
                 row["labour_tightness_relative_to_own_history_z"]) / 2.0,
                places=10)
            self.assertIsNone(row["economic_cycle_certified"])
            self.assertIsNone(row["fx_currency_strength_score"])
            self.assertIsNone(row["fx_directional_bias"])
            self.assertIsNone(row["cb_pricing_signal"])
            self.assertFalse(row["candidate_for_pair_ranking"])

    def test_real_data_quality_gates_are_exposed_not_silently_removed(self):
        report = build(self.raw)
        self.assertEqual(report["summary"]["countries_with_estimated_source_axes"], 1)
        self.assertEqual(report["summary"]["countries_with_GDP_measurement_caveats"], 2)
        rows = report["countries"]
        self.assertEqual(rows["USD"]["qualitative_quality"], "ESTIMATED_RESEARCH_ONLY")
        self.assertTrue(rows["USD"]["dimensions"]["labour"]["is_estimate"])
        self.assertTrue(rows["USD"]["dimensions"]["inflation"]["is_estimate"])
        self.assertTrue(rows["USD"]["dimensions"]["inflation"]["source_evidence_url"].startswith("https://www.bls.gov/"))
        for c in ("EUR", "CHF"):
            self.assertEqual(rows[c]["qualitative_quality"],
                             "GDP_DEFINITION_CAVEAT_RESEARCH_ONLY")
            self.assertFalse(rows[c]["dimensions"]["growth"]["is_estimate"])
            self.assertTrue(rows[c]["dimensions"]["growth"]["definition_caveats"])
        for c in set(FX) - {"USD", "EUR", "CHF"}:
            self.assertEqual(rows[c]["quality_flags"], [])
            self.assertEqual(rows[c]["qualitative_quality"],
                             "REVISED_OR_WEB_RESEARCH_NOT_PIT")

    def test_inflation_does_not_boost_or_reduce_activity_proxy(self):
        first = build(self.raw)["countries"]["CAD"]
        updated = copy.deepcopy(self.raw)
        original = updated["inflation_labour"]["CAD.inflation"]["research_robust_z"]
        replacement = -3.0 if original > 0 else 3.0
        updated["inflation_labour"]["CAD.inflation"]["research_robust_z"] = replacement
        after = build(updated)["countries"]["CAD"]
        self.assertEqual(first["illustrative_activity_labour_balance_z"],
                         after["illustrative_activity_labour_balance_z"])
        self.assertNotEqual(first["inflation_pressure_relative_to_own_history_z"],
                            after["inflation_pressure_relative_to_own_history_z"])
        self.assertIsNone(after["fx_currency_strength_score"])

    def test_higher_unemployment_reverses_into_weaker_labour_support(self):
        before = build(self.raw)["countries"]["AUD"]
        modified = copy.deepcopy(self.raw)
        l = modified["inflation_labour"]["AUD.labour"]
        l["research_robust_z"] = min(3.0, l["research_robust_z"] + 0.75)
        after = build(modified)["countries"]["AUD"]
        self.assertLessEqual(after["labour_tightness_relative_to_own_history_z"],
                             before["labour_tightness_relative_to_own_history_z"])
        self.assertLessEqual(after["illustrative_activity_labour_balance_z"],
                             before["illustrative_activity_labour_balance_z"])

    def test_only_true_bls_shut_down_estimate_accepted(self):
        bad = copy.deepcopy(self.raw)
        bad["us_bls_shutdown_research_estimates"].pop("USD.labour")
        with self.assertRaisesRegex(ValueError, "missing strict z"):
            build(bad)
        bad = copy.deepcopy(self.raw)
        bad["us_bls_shutdown_research_estimates"]["USD.inflation"]["original_missing_value_imputed"] = True
        with self.assertRaisesRegex(ValueError, "US October 2025 provenance"):
            build(bad)
        bad = copy.deepcopy(self.raw)
        bad["us_bls_shutdown_research_estimates"]["USD.inflation"]["missing_calendar_periods"] = ["2025-09", "2025-10"]
        with self.assertRaisesRegex(ValueError, "US October 2025 provenance"):
            build(bad)
        bad = copy.deepcopy(self.raw)
        bad["us_bls_shutdown_research_estimates"]["CHF.inflation"] = {}
        with self.assertRaisesRegex(ValueError, "scope"):
            build(bad)

    def test_unemployment_series_semantic_and_sign_spoofing_rejected(self):
        bad = copy.deepcopy(self.raw)
        bad["inflation_labour"]["EUR.labour"]["canonical_series_id"] = "SOME_EMPLOYMENT_LEVEL"
        with self.assertRaisesRegex(ValueError, "unemployment rate"):
            build(bad)
        bad = copy.deepcopy(self.raw)
        bad["inflation_labour"]["EUR.inflation"]["economic_interpretation"] = "STRONG_EUR_IF_HIGH_CPI"
        with self.assertRaisesRegex(ValueError, "polarity"):
            build(bad)
        bad = copy.deepcopy(self.raw)
        bad["inflation_labour"]["EUR.labour"]["eligible_for_macro_score"] = True
        with self.assertRaisesRegex(ValueError, "unapproved pillar"):
            build(bad)

    def test_growth_first_web_and_euro_swiss_quality_gates(self):
        bad = copy.deepcopy(self.raw)
        bad["growth_quarterly_gdp_initial_web_research_features"]["USD"]["actual_PIT_backtest_eligible"] = True
        with self.assertRaisesRegex(ValueError, "GDP first-release research-only"):
            build(bad)
        bad = copy.deepcopy(self.raw)
        bad["growth_quarterly_gdp_initial_web_research_features"]["CHF"]["growth_definition_caveats"] = []
        with self.assertRaisesRegex(ValueError, "quality flags"):
            build(bad)
        bad = copy.deepcopy(self.raw)
        bad["growth_quarterly_gdp_initial_web_research_features"]["CAD"]["research_robust_growth_z"] = None
        with self.assertRaisesRegex(ValueError, "finite clipped"):
            build(bad)

    def test_no_legacy_24_numeric_targets_baked_into_new_formula(self):
        report = build(self.raw)
        self.assertTrue(report["scope"]["activity_is_hypothetical_within_country_not_rank_comparable"])
        self.assertEqual(report["scope"]["activity_weights"]["inflation_in_activity"], 0.0)
        self.assertTrue(report["rates_CB_pricing_positioning_not_included"])
        self.assertTrue(report["economic_axis_math_not_validated_against_out_of_sample_events"])

    def test_future_audit_rejected(self):
        fake = copy.deepcopy(self.raw)
        fake["checked_as_of"] = "2099-01-01"
        with self.assertRaisesRegex(ValueError, "future"):
            build(fake)

    def test_no_mutation_core_D_or_28_pairs(self):
        root = ROOT / "live_data/sections"
        files = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        before = {p: (root / p).read_bytes() for p in files}
        report = run(as_of=self.as_of)
        after = {p: (root / p).read_bytes() for p in files}
        self.assertEqual(before, after)
        self.assertEqual(report["receipt_sha256"], build(self.raw)["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
